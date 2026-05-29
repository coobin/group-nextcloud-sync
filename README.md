# group-nextcloud-sync

`group-nextcloud-sync` reads users and department groups from OpenLDAP and syncs
them into Nextcloud.

LDAP is the source of truth. The upstream HR system should sync into LDAP first
using the separate `xrxs2ldap` service; this project no longer calls
Xinrenxinshi directly.

## Sync Rules

1. LDAP users with `employeeType=active` are added to the default Nextcloud group
   (`ALL` by default).
2. LDAP `posixGroup` entries are matched to existing Nextcloud groups by
   display name.
3. LDAP group membership comes from `memberUid`; users can map to multiple
   Nextcloud groups.
4. Missing Nextcloud groups are not created, except the default group.
5. For managed groups, stale Nextcloud memberships are removed.
6. LDAP users with inactive status values are removed from managed groups.
7. Inactive LDAP users are disabled in Nextcloud when
   `NEXTCLOUD_DISABLE_INACTIVE_USERS=true`.

## Data Source

Default source:

- `HR_SOURCE=ldap`: reads users from `ou=people` and groups from `ou=groups`.

Development source:

- `HR_SOURCE=json_file`: reads `samples/hr_data.json`.

The old `xinrenxinshi` adapter is intentionally not wired in the CLI anymore.
Use `xrxs2ldap` to populate LDAP from Xinrenxinshi.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
```

Preview without writing:

```bash
group-nextcloud-sync --dry-run
```

Run for real:

```bash
DRY_RUN=false group-nextcloud-sync
```

Compatible command names:

- `oidc-necxtcloud`
- `ldap2nextcloud`

## Key Configuration

```dotenv
HR_SOURCE=ldap
DRY_RUN=true

LDAP_URI=ldap://10.1.6.99:1389
LDAP_BASE_DN=dc=chencytech,dc=com
LDAP_BIND_DN=cn=admin,dc=chencytech,dc=com
LDAP_BIND_PASSWORD=
LDAP_PEOPLE_OU=ou=people
LDAP_GROUPS_OU=ou=groups
LDAP_USER_FILTER=(objectClass=inetOrgPerson)
LDAP_GROUP_FILTER=(objectClass=posixGroup)
LDAP_UID_ATTR=uid
LDAP_DISPLAY_NAME_ATTR=displayName
LDAP_EMAIL_ATTR=mail
LDAP_STATUS_ATTR=employeeType
LDAP_INACTIVE_STATUS_VALUES=inactive,deactive,disabled

NEXTCLOUD_DB_HOST=db
NEXTCLOUD_DB_PORT=3306
NEXTCLOUD_DB_NAME=nextcloud
NEXTCLOUD_DB_USER=nextcloud
NEXTCLOUD_DB_PASSWORD=
NEXTCLOUD_DEFAULT_GROUP=ALL
NEXTCLOUD_DEPARTMENT_GROUP_ALIASES=交付组=服务交付部,运维组=服务交付部

NEXTCLOUD_DISABLE_INACTIVE_USERS=true
NEXTCLOUD_DISABLE_INACTIVE_METHOD=db
NEXTCLOUD_BASE_URL=https://nextcloud.example.com
NEXTCLOUD_ADMIN_USER=
NEXTCLOUD_ADMIN_PASSWORD=
```

Group memberships are still written directly to the Nextcloud database, matching
the original project behavior. Account disabling defaults to the same database
path by setting `oc_preferences` `core/enabled=false`, matching Nextcloud's own
`occ user:disable` behavior. If you prefer the Provisioning API, set
`NEXTCLOUD_DISABLE_INACTIVE_METHOD=api` and configure admin credentials:

```text
PUT /ocs/v1.php/cloud/users/{userid}/disable
```

## Log Output

The program prints:

- `[INFO]`: state loading and mapping information
- `[WARN]`: missing users, unmatched groups, skipped disables
- `[ACTION]`: writes or dry-run writes
- `[ERROR]`: failed sync summary
- `[SUMMARY]`: final counters, including disabled users

## Safety Notes

Keep `DRY_RUN=true` until LDAP matching, group changes, and inactive-user disable
actions look correct.

The repository ignores local secrets such as `.env`, private keys, virtual
environments, and build archives.
