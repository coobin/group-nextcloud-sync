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
    ldap_uri: str
    ldap_bind_dn: str
    ldap_bind_password: str
    ldap_base_dn: str
    ldap_people_ou: str
    ldap_groups_ou: str
    ldap_user_filter: str
    ldap_group_filter: str
    ldap_uid_attr: str
    ldap_display_name_attr: str
    ldap_email_attr: str
    ldap_employee_number_attr: str
    ldap_department_attr: str
    ldap_status_attr: str
    ldap_inactive_status_values: set[str]
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
    nextcloud_disable_inactive_users: bool
    nextcloud_disable_inactive_method: str
    nextcloud_base_url: str | None
    nextcloud_admin_user: str | None
    nextcloud_admin_password: str | None
    nextcloud_api_timeout_seconds: int

    @property
    def ldap_people_base_dn(self) -> str:
        return f"{self.ldap_people_ou},{self.ldap_base_dn}"

    @property
    def ldap_groups_base_dn(self) -> str:
        return f"{self.ldap_groups_ou},{self.ldap_base_dn}"


def load_settings() -> Settings:
    ldap_base_dn = _env("LDAP_BASE_DN", "dc=chencytech,dc=com") or "dc=chencytech,dc=com"
    return Settings(
        hr_source=_env("HR_SOURCE", "ldap") or "ldap",
        dry_run=_bool_env("DRY_RUN", True),
        json_file_path=_env("JSON_FILE_PATH", "samples/hr_data.json"),
        ldap_uri=_env("LDAP_URI", "ldap://localhost:1389") or "ldap://localhost:1389",
        ldap_bind_dn=_env("LDAP_BIND_DN", f"cn=admin,{ldap_base_dn}") or f"cn=admin,{ldap_base_dn}",
        ldap_bind_password=_env("LDAP_BIND_PASSWORD", "") or "",
        ldap_base_dn=ldap_base_dn,
        ldap_people_ou=_env("LDAP_PEOPLE_OU", "ou=people") or "ou=people",
        ldap_groups_ou=_env("LDAP_GROUPS_OU", "ou=groups") or "ou=groups",
        ldap_user_filter=_env("LDAP_USER_FILTER", "(objectClass=inetOrgPerson)") or "(objectClass=inetOrgPerson)",
        ldap_group_filter=_env("LDAP_GROUP_FILTER", "(objectClass=posixGroup)") or "(objectClass=posixGroup)",
        ldap_uid_attr=_env("LDAP_UID_ATTR", "uid") or "uid",
        ldap_display_name_attr=_env("LDAP_DISPLAY_NAME_ATTR", "displayName") or "displayName",
        ldap_email_attr=_env("LDAP_EMAIL_ATTR", "mail") or "mail",
        ldap_employee_number_attr=_env("LDAP_EMPLOYEE_NUMBER_ATTR", "employeeNumber") or "employeeNumber",
        ldap_department_attr=_env("LDAP_DEPARTMENT_ATTR", "departmentNumber") or "departmentNumber",
        ldap_status_attr=_env("LDAP_STATUS_ATTR", "employeeType") or "employeeType",
        ldap_inactive_status_values={
            item.strip().lower()
            for item in (_env("LDAP_INACTIVE_STATUS_VALUES", "inactive,deactive,disabled") or "").split(",")
            if item.strip()
        },
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
        nextcloud_disable_inactive_users=_bool_env("NEXTCLOUD_DISABLE_INACTIVE_USERS", True),
        nextcloud_disable_inactive_method=(
            _env("NEXTCLOUD_DISABLE_INACTIVE_METHOD", "db") or "db"
        ).strip().lower(),
        nextcloud_base_url=_env("NEXTCLOUD_BASE_URL"),
        nextcloud_admin_user=_env("NEXTCLOUD_ADMIN_USER"),
        nextcloud_admin_password=_env("NEXTCLOUD_ADMIN_PASSWORD"),
        nextcloud_api_timeout_seconds=_int_env("NEXTCLOUD_API_TIMEOUT_SECONDS", 30),
    )
