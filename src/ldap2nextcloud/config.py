from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    return int(value)


def _mapping_env(name: str) -> dict[str, str]:
    value = _env(name, "") or ""
    mapping: dict[str, str] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        source, separator, target = item.partition("=")
        if not separator:
            raise ValueError(f"{name} item must use source=target format: {item!r}")
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise ValueError(f"{name} item cannot contain empty source or target: {item!r}")
        mapping[source] = target
    return mapping


@dataclass(slots=True)
class Settings:
    hr_source: str
    dry_run: bool
    json_file_path: str | None
    xrxs_base_url: str | None
    xrxs_token_url: str | None
    xrxs_departments_url: str | None
    xrxs_employees_url: str | None
    xrxs_app_id: str | None
    xrxs_app_secret: str | None
    xrxs_company_id: str | None
    nextcloud_db_host: str
    nextcloud_db_port: int
    nextcloud_db_name: str
    nextcloud_db_user: str
    nextcloud_db_password: str
    nextcloud_default_group: str
    nextcloud_department_group_aliases: dict[str, str]


def load_settings() -> Settings:
    return Settings(
        hr_source=_env("HR_SOURCE", "json_file") or "json_file",
        dry_run=_bool_env("DRY_RUN", True),
        json_file_path=_env("JSON_FILE_PATH", "samples/hr_data.json"),
        xrxs_base_url=_env("XRXS_BASE_URL", "https://api.xinrenxinshi.com"),
        xrxs_token_url=_env("XRXS_TOKEN_URL"),
        xrxs_departments_url=_env("XRXS_DEPARTMENTS_URL"),
        xrxs_employees_url=_env("XRXS_EMPLOYEES_URL"),
        xrxs_app_id=_env("XRXS_APP_ID"),
        xrxs_app_secret=_env("XRXS_APP_SECRET"),
        xrxs_company_id=_env("XRXS_COMPANY_ID"),
        nextcloud_db_host=_env("NEXTCLOUD_DB_HOST", "db") or "db",
        nextcloud_db_port=_int_env("NEXTCLOUD_DB_PORT", 3306),
        nextcloud_db_name=_env("NEXTCLOUD_DB_NAME", "nextcloud") or "nextcloud",
        nextcloud_db_user=_env("NEXTCLOUD_DB_USER", "nextcloud") or "nextcloud",
        nextcloud_db_password=_env("NEXTCLOUD_DB_PASSWORD", "") or "",
        nextcloud_default_group=_env("NEXTCLOUD_DEFAULT_GROUP", "ALL") or "ALL",
        nextcloud_department_group_aliases=_mapping_env("NEXTCLOUD_DEPARTMENT_GROUP_ALIASES"),
    )
