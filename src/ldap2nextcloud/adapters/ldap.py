from __future__ import annotations

from collections import defaultdict

from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.utils.dn import parse_dn

from ldap2nextcloud.adapters.base import HrAdapter
from ldap2nextcloud.config import Settings
from ldap2nextcloud.models import Department, Employee, HrSnapshot


class LdapAdapter(HrAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch_snapshot(self) -> HrSnapshot:
        server = Server(self.settings.ldap_uri, get_info=ALL)
        connection = Connection(
            server,
            user=self.settings.ldap_bind_dn,
            password=self.settings.ldap_bind_password,
            auto_bind=True,
        )
        try:
            departments, member_groups = self._load_groups(connection)
            employees = self._load_employees(connection, member_groups)
            return HrSnapshot(departments=departments, employees=employees)
        finally:
            connection.unbind()

    def _load_groups(self, connection: Connection) -> tuple[list[Department], dict[str, list[str]]]:
        connection.search(
            search_base=self.settings.ldap_groups_base_dn,
            search_filter=self.settings.ldap_group_filter,
            search_scope=SUBTREE,
            attributes=["cn", "memberUid"],
        )

        group_dns = {entry.entry_dn for entry in connection.entries}
        departments: list[Department] = []
        member_groups: dict[str, list[str]] = defaultdict(list)

        for entry in connection.entries:
            group_dn = entry.entry_dn
            parent_dn = self._parent_group_dn(group_dn, group_dns)
            departments.append(
                Department(
                    id=group_dn,
                    name=self._first_rdn_value(group_dn) or self._first_attr(entry, "cn") or group_dn,
                    parent_id=parent_dn,
                )
            )
            if "memberUid" in entry:
                for uid in entry["memberUid"].values:
                    uid_text = str(uid).strip()
                    if uid_text:
                        member_groups[uid_text].append(group_dn)

        return departments, {uid: self._deepest_first(group_dns) for uid, group_dns in member_groups.items()}

    def _load_employees(
        self,
        connection: Connection,
        member_groups: dict[str, list[str]],
    ) -> list[Employee]:
        connection.search(
            search_base=self.settings.ldap_people_base_dn,
            search_filter=self.settings.ldap_user_filter,
            search_scope=SUBTREE,
            attributes=[
                self.settings.ldap_uid_attr,
                self.settings.ldap_display_name_attr,
                self.settings.ldap_email_attr,
                self.settings.ldap_employee_number_attr,
                self.settings.ldap_department_attr,
                self.settings.ldap_status_attr,
                "cn",
                "title",
            ],
        )

        employees: list[Employee] = []
        for entry in connection.entries:
            uid = self._first_attr(entry, self.settings.ldap_uid_attr)
            if not uid:
                continue
            status = (self._first_attr(entry, self.settings.ldap_status_attr) or "active").lower()
            group_ids = tuple(member_groups.get(uid, []))
            department_id = group_ids[0] if group_ids else None
            employees.append(
                Employee(
                    id=self._first_attr(entry, self.settings.ldap_employee_number_attr) or uid,
                    username=uid,
                    display_name=(
                        self._first_attr(entry, self.settings.ldap_display_name_attr)
                        or self._first_attr(entry, "cn")
                        or uid
                    ),
                    email=self._first_attr(entry, self.settings.ldap_email_attr),
                    department_id=department_id,
                    department_ids=group_ids,
                    title=self._first_attr(entry, "title"),
                    active=status not in self.settings.ldap_inactive_status_values,
                )
            )
        return employees

    def _parent_group_dn(self, group_dn: str, group_dns: set[str]) -> str | None:
        parts = group_dn.split(",", 1)
        if len(parts) != 2:
            return None
        parent_dn = parts[1]
        if parent_dn == self.settings.ldap_groups_base_dn:
            return None
        return parent_dn if parent_dn in group_dns else None

    def _first_rdn_value(self, dn: str) -> str | None:
        try:
            parsed = parse_dn(dn)
        except Exception:
            return None
        if not parsed:
            return None
        attr, value, _separator = parsed[0]
        return value if attr.lower() == "cn" and value else None

    def _first_attr(self, entry: object, attr: str) -> str | None:
        if not attr or attr not in entry:
            return None
        values = [str(value).strip() for value in entry[attr].values if str(value).strip()]
        return values[0] if values else None

    def _deepest_first(self, group_dns: list[str]) -> list[str]:
        return sorted(set(group_dns), key=lambda dn: (-dn.count(","), dn))
