from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pymysql
import pymysql.cursors

from ldap2nextcloud.config import Settings
from ldap2nextcloud.models import HrSnapshot


@dataclass(slots=True)
class GroupSyncStats:
    departments_seen: int = 0
    active_users_seen: int = 0
    inactive_users_seen: int = 0
    users_seen: int = 0
    users_missing: int = 0
    users_resolved_by_email: int = 0
    users_without_matching_department_group: int = 0
    unmatched_only_default_users: int = 0
    unmatched_with_existing_groups: int = 0
    duplicate_display_names: int = 0
    managed_groups: int = 0
    memberships_added: int = 0
    memberships_removed: int = 0


class NextcloudGroupSyncService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def sync(self, snapshot: HrSnapshot) -> GroupSyncStats:
        stats = GroupSyncStats()
        unmatched_only_default_details: list[tuple[str, str, str]] = []
        stats.departments_seen = len(snapshot.departments)
        self._ensure_group(self.settings.nextcloud_default_group)

        groups = self._load_groups()
        users = self._load_users()
        users_by_email = self._load_users_by_email(users)
        memberships = self._load_group_memberships()
        membership_count = sum(len(gids) for gids in memberships.values())
        self._log(
            "INFO",
            "state loaded "
            f"departments={len(snapshot.departments)} employees={len(snapshot.employees)} "
            f"groups={len(groups)} nextcloud_users={len(users)} memberships={membership_count}",
        )

        departments_by_id = {department.id: department for department in snapshot.departments}
        target_display_names = {
            self.settings.nextcloud_department_group_aliases.get(department.name, department.name)
            for department in snapshot.departments
        }
        group_gid_by_display_name, duplicate_display_names = self._index_groups_by_display_name(
            groups,
            target_display_names,
        )
        stats.duplicate_display_names = len(duplicate_display_names)
        managed_department_gids = set(group_gid_by_display_name.values())
        managed_gids = managed_department_gids | {self.settings.nextcloud_default_group}
        stats.managed_groups = len(managed_gids)

        for employee in snapshot.employees:
            target_uid = self._resolve_target_uid(employee.username, employee.email, users, users_by_email, stats)
            if not employee.active:
                stats.inactive_users_seen += 1
                self._remove_user_from_managed_groups(target_uid, memberships, managed_gids, stats)
                continue

            stats.users_seen += 1
            stats.active_users_seen += 1
            if target_uid not in users:
                stats.users_missing += 1
                self._log("WARN", f"user missing in nextcloud uid={employee.username}")
                continue

            desired_gids = {self.settings.nextcloud_default_group}
            department = departments_by_id.get(employee.department_id or "")
            if department is not None:
                target_display_name = self.settings.nextcloud_department_group_aliases.get(
                    department.name,
                    department.name,
                )
                matched_gid = group_gid_by_display_name.get(target_display_name)
                if matched_gid:
                    desired_gids.add(matched_gid)
                else:
                    stats.users_without_matching_department_group += 1
                    current_groups = memberships.get(target_uid, set())
                    has_other_groups = any(gid != self.settings.nextcloud_default_group for gid in current_groups)
                    if has_other_groups:
                        stats.unmatched_with_existing_groups += 1
                    else:
                        stats.unmatched_only_default_users += 1
                        unmatched_only_default_details.append(
                            (target_uid, department.name, target_display_name)
                        )

            self._sync_user_memberships(target_uid, desired_gids, managed_gids, memberships, stats)

        for display_name, gids in sorted(duplicate_display_names.items()):
            self._log(
                "WARN",
                "duplicate group display name ignored "
                f"displayName={display_name} gids={', '.join(sorted(gids))}"
            )

        if stats.users_without_matching_department_group > 0:
            self._log(
                "WARN",
                "department group unmatched summary "
                f"total={stats.users_without_matching_department_group} "
                f"only_default={stats.unmatched_only_default_users} "
                f"with_existing_groups={stats.unmatched_with_existing_groups}",
            )
            for uid, department, target in sorted(unmatched_only_default_details):
                self._log(
                    "WARN",
                    "only default group "
                    f"uid={uid} department={department} target={target}",
                )
        return stats

    def _index_groups_by_display_name(
        self,
        groups: dict[str, str],
        department_names: set[str],
    ) -> tuple[dict[str, str], dict[str, list[str]]]:
        gids_by_display_name: dict[str, list[str]] = defaultdict(list)
        for gid, display_name in groups.items():
            if display_name in department_names:
                gids_by_display_name[display_name].append(gid)

        unique = {
            display_name: gids[0]
            for display_name, gids in gids_by_display_name.items()
            if len(gids) == 1
        }
        duplicates = {
            display_name: gids
            for display_name, gids in gids_by_display_name.items()
            if len(gids) > 1
        }
        return unique, duplicates

    def _sync_user_memberships(
        self,
        uid: str,
        desired_gids: set[str],
        managed_gids: set[str],
        memberships: dict[str, set[str]],
        stats: GroupSyncStats,
    ) -> None:
        current = memberships.get(uid, set())
        for gid in sorted(desired_gids - current):
            self._add_user_to_group(uid, gid)
            memberships[uid].add(gid)
            stats.memberships_added += 1

        for gid in sorted((current & managed_gids) - desired_gids):
            self._remove_user_from_group(uid, gid)
            memberships[uid].discard(gid)
            stats.memberships_removed += 1

    def _remove_user_from_managed_groups(
        self,
        uid: str,
        memberships: dict[str, set[str]],
        managed_gids: set[str],
        stats: GroupSyncStats,
    ) -> None:
        for gid in sorted(memberships.get(uid, set()) & managed_gids):
            self._remove_user_from_group(uid, gid)
            memberships[uid].discard(gid)
            stats.memberships_removed += 1

    def _ensure_group(self, gid: str) -> None:
        if gid in self._load_groups():
            return
        if self.settings.dry_run:
            self._log("ACTION", f"DRY-RUN create default group gid={gid}")
            return
        self._execute(
            "INSERT INTO oc_groups (gid, displayname) VALUES (%s, %s)",
            (gid, gid),
        )
        self._log("ACTION", f"created group gid={gid}")

    def _add_user_to_group(self, uid: str, gid: str) -> None:
        if self.settings.dry_run:
            self._log("ACTION", f"DRY-RUN add uid={uid} gid={gid}")
            return
        self._execute(
            "INSERT IGNORE INTO oc_group_user (gid, uid) VALUES (%s, %s)",
            (gid, uid),
        )
        self._log("ACTION", f"added uid={uid} gid={gid}")

    def _remove_user_from_group(self, uid: str, gid: str) -> None:
        if self.settings.dry_run:
            self._log("ACTION", f"DRY-RUN remove uid={uid} gid={gid}")
            return
        self._execute(
            "DELETE FROM oc_group_user WHERE gid = %s AND uid = %s",
            (gid, uid),
        )
        self._log("ACTION", f"removed uid={uid} gid={gid}")

    def _load_groups(self) -> dict[str, str]:
        rows = self._query("SELECT gid, displayname FROM oc_groups")
        return {row["gid"]: row["displayname"] for row in rows}

    def _load_users(self) -> set[str]:
        rows = self._query("SELECT uid FROM oc_users")
        return {row["uid"] for row in rows}

    def _load_users_by_email(self, users: set[str]) -> dict[str, list[str]]:
        rows = self._query(
            "SELECT p.userid, p.configvalue "
            "FROM oc_preferences p "
            "JOIN oc_users u ON u.uid = p.userid "
            "WHERE p.appid='settings' AND p.configkey='email' AND p.configvalue <> ''"
        )
        users_by_email: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            uid = row["userid"]
            email = row["configvalue"].strip().lower()
            if uid in users and email:
                users_by_email[email].append(uid)
        return users_by_email

    def _resolve_target_uid(
        self,
        username: str,
        email: str | None,
        users: set[str],
        users_by_email: dict[str, list[str]],
        stats: GroupSyncStats,
    ) -> str:
        if username in users:
            return username
        if not email:
            return username

        candidates = sorted(set(users_by_email.get(email.strip().lower(), [])))
        if len(candidates) == 1:
            resolved_uid = candidates[0]
            stats.users_resolved_by_email += 1
            self._log(
                "INFO",
                f"user mapped by email username={username} resolved_uid={resolved_uid} email={email}",
            )
            return resolved_uid
        if len(candidates) > 1:
            self._log(
                "WARN",
                f"user email matched multiple nextcloud users username={username} email={email} candidates={','.join(candidates)}",
            )
        return username

    def _load_group_memberships(self) -> dict[str, set[str]]:
        rows = self._query("SELECT uid, gid FROM oc_group_user")
        memberships: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            memberships[row["uid"]].add(row["gid"])
        return memberships

    def _query(self, sql: str) -> list[dict[str, str]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        return [{key: str(value) for key, value in row.items()} for row in rows]

    def _execute(self, sql: str, params: tuple[str, ...]) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
            connection.commit()

    def _connect(self):
        if not self.settings.nextcloud_db_password:
            raise RuntimeError("NEXTCLOUD_DB_PASSWORD is required")
        return pymysql.connect(
            host=self.settings.nextcloud_db_host,
            port=self.settings.nextcloud_db_port,
            user=self.settings.nextcloud_db_user,
            password=self.settings.nextcloud_db_password,
            database=self.settings.nextcloud_db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _log(self, level: str, message: str) -> None:
        print(f"[{level}] {message}")
