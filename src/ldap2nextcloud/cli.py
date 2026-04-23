from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ldap2nextcloud.adapters.json_file import JsonFileAdapter
from ldap2nextcloud.adapters.xinrenxinshi import XinrenxinshiAdapter
from ldap2nextcloud.config import load_settings
from ldap2nextcloud.sync import NextcloudGroupSyncService


DEFAULT_TIMEZONE = timezone(timedelta(hours=8))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync HR users into Nextcloud groups by display name.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    return parser


def load_dotenv_file(file_path: str = ".env") -> None:
    env_file = Path(file_path)
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _timestamp() -> str:
    return datetime.now(DEFAULT_TIMEZONE).isoformat(timespec="seconds")


def _build_adapter(settings):
    if settings.hr_source == "json_file":
        return JsonFileAdapter(settings.json_file_path or "samples/hr_data.json")
    if settings.hr_source == "xinrenxinshi":
        return XinrenxinshiAdapter(settings)
    raise ValueError(f"Unsupported HR_SOURCE: {settings.hr_source}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    load_dotenv_file()
    settings = load_settings()
    if args.dry_run:
        settings.dry_run = True

    print(
        f"{_timestamp()} [INFO] sync started "
        f"source={settings.hr_source} dry_run={settings.dry_run} "
        f"default_group={settings.nextcloud_default_group}"
    )
    snapshot = _build_adapter(settings).fetch_snapshot()
    print(
        f"{_timestamp()} [INFO] hr snapshot loaded "
        f"departments={len(snapshot.departments)} employees={len(snapshot.employees)}"
    )
    try:
        stats = NextcloudGroupSyncService(settings).sync(snapshot)
    except Exception as exc:
        print(f"{_timestamp()} [ERROR] sync failed type={type(exc).__name__} message={exc}")
        return 1
    print(
        f"{_timestamp()} [SUMMARY] sync finished:",
        {
            "departments_seen": stats.departments_seen,
            "active_users_seen": stats.active_users_seen,
            "inactive_users_seen": stats.inactive_users_seen,
            "users_seen": stats.users_seen,
            "users_missing": stats.users_missing,
            "users_resolved_by_email": stats.users_resolved_by_email,
            "users_without_matching_department_group": stats.users_without_matching_department_group,
            "unmatched_only_default_users": stats.unmatched_only_default_users,
            "unmatched_with_existing_groups": stats.unmatched_with_existing_groups,
            "duplicate_display_names": stats.duplicate_display_names,
            "managed_groups": stats.managed_groups,
            "memberships_added": stats.memberships_added,
            "memberships_removed": stats.memberships_removed,
            "dry_run": settings.dry_run,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
