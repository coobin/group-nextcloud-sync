# group-nextcloud-sync

`group-nextcloud-sync` 用于把 HR 人员信息同步到 Nextcloud 现有用户组。

它不负责认证登录，认证由 OIDC（Authelia + Nextcloud user_oidc）完成；本项目只负责组成员关系维护。

## 同步规则

1. 所有 HR 中 `active=true` 的员工都加入默认组（默认 `ALL`）。
2. 按“HR 部门名 -> Nextcloud 组显示名（displayname）”匹配部门组。
3. 仅当匹配到唯一显示名组时才加入。
4. 未匹配到部门组时，不创建新组，用户只保留默认组。
5. 对本工具管理范围内的组，会自动移除旧的部门组成员关系。

## 数据来源

- `HR_SOURCE=json_file`：读取 `samples/hr_data.json`。
- `HR_SOURCE=xinrenxinshi`：调用薪人薪事 API 拉取部门和人员。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
```

先预览（不写入）：

```bash
group-nextcloud-sync --dry-run
```

正式执行：

```bash
DRY_RUN=false group-nextcloud-sync
```

兼容旧命令：

- `oidc-necxtcloud`
- `ldap2nextcloud`

## 关键配置

```dotenv
HR_SOURCE=xinrenxinshi
XRXS_BASE_URL=https://api.xinrenxinshi.com
XRXS_APP_ID=
XRXS_APP_SECRET=
XRXS_COMPANY_ID=

NEXTCLOUD_DB_HOST=db
NEXTCLOUD_DB_PORT=3306
NEXTCLOUD_DB_NAME=nextcloud
NEXTCLOUD_DB_USER=nextcloud
NEXTCLOUD_DB_PASSWORD=
NEXTCLOUD_DEFAULT_GROUP=ALL
NEXTCLOUD_DEPARTMENT_GROUP_ALIASES=交付组=服务交付部,运维组=服务交付部
```

完整配置见 [.env.example](.env.example)。

## 日志说明

程序输出按级别标识：

- `[INFO]`：流程阶段与基础状态
- `[WARN]`：缺失用户、未匹配部门组等可继续问题
- `[ERROR]`：同步失败摘要
- `[SUMMARY]`：本轮统计结果

## 开源前安全检查

已默认通过 `.gitignore` 排除以下内容：

- `.env`
- 本地虚拟环境与缓存
- 私钥/证书文件（`*.key`, `*.pem`, `*.crt`, `*.p12`）
- 打包产物（`*.tar.gz`, `*.tgz`, `*.zip`）

请确认提交前仅保留示例配置，不提交任何真实账号、密码、密钥或 token。
