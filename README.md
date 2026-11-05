# Template-Backup

```
Python 備份模板
備份 → 壓縮 → 保留 N 份輪替 → 上傳（rclone/S3）→ 通知、cron 範例、還原步驟文件
```

## 目錄

- [目錄結構](#目錄結構)
- [基於此模板建立新專案](#基於此模板建立新專案)
- [備份流程](#備份流程)
- [設定](#設定)
- [備份 job](#備份-job)
- [上傳](#上傳)
- [指令](#指令)
- [Docker 與排程](#docker-與排程)
- [擴充](#擴充)
- [注意事項](#注意事項)

## 目錄結構

```
Template-Backup/
├── conf/
│   └── config.ini.default   # 設定 + job 範本（複製為 config.ini）
├── cron/
│   └── backup.cron.example  # crontab 範例
├── docker/
│   └── Dockerfile           # 內含 mysqldump、pg_dump、rclone（mongodump 選用）
├── src/
│   ├── __init__.py          # 讀取設定（get_setting / get_int / get_bool）
│   ├── __main__.py          # 進入點：backup / list / verify / restore
│   ├── backup.py            # 流程：dump → checksum → 輪替 → 上傳 → 通知
│   ├── rotation.py          # 依檔名時間戳保留最新 N 份
│   ├── util.py              # 時間戳、sha256、子程序管線
│   ├── sources/             # files / mysql / postgres / mongo
│   ├── uploaders/           # none / rclone / s3
│   └── notify/              # console / telegram / mail
├── tests/
├── RESTORE.md               # 還原步驟與演練
├── .env.default             # 機密（DB 密碼、S3 金鑰、通知 token）
├── docker-compose.yml
├── requirements.txt
├── requirements-test.txt
└── pytest.ini
```

## 基於此模板建立新專案

```bash
git clone <此模板 URL> your-new-project
cd your-new-project
rm -rf .git && git init          # 不保留模板歷史
cp conf/config.ini.default conf/config.ini
cp .env.default .env
```

## 備份流程

```
[job] dump（已壓縮）→ 寫入 .sha256 → 本機輪替（保留 KEEP_LOCAL）
      → 上傳備份檔與 .sha256 → 遠端輪替（保留 KEEP_REMOTE）
全部 job 完成 → 彙整結果通知（NOTIFY_ON）
```

- 檔名：`data/backups/<job>/<job>_<YYYYmmdd-HHMMSS>.<ext>`（UTC），輪替以檔名時間戳判斷
- dump 失敗時刪除不完整檔案，不進入輪替（不會因失敗把舊備份擠掉）
- 單一 job 失敗不影響其他 job；任一失敗時結束碼為 `1`

## 設定

讀取順序：**環境變數 > `conf/config.ini` > 預設值**。

| 區段 / 鍵 | 說明 | 預設 |
|---|---|---|
| `[BACKUP] BACKUP_NAME` | 通知標題中的名稱 | `backup` |
| `[BACKUP] BACKUP_DIR` | 本機備份目錄 | `data/backups` |
| `[BACKUP] KEEP_LOCAL` / `KEEP_REMOTE` | 預設保留份數（`0` = 不刪除） | `7` / `30` |
| `[UPLOAD] UPLOADER` | `none` / `rclone` / `s3` | `none` |
| `[UPLOAD] RCLONE_REMOTE` | 例如 `b2:my-bucket/backups` | — |
| `[UPLOAD] S3_BUCKET` / `S3_PREFIX` / `S3_ENDPOINT_URL` | S3 / 相容服務 | — / `backups` / — |
| `[NOTIFY] NOTIFY_CHANNELS` | `console,telegram,mail` | `console` |
| `[NOTIFY] NOTIFY_ON` | `always` / `failure` / `never` | `always` |

## 備份 job

每個 `[job:<名稱>]` 一項；機密欄位填的是**環境變數名稱**，值放 `.env`：

| type | 參數 | 輸出 |
|---|---|---|
| `files` | `paths`（逗號分隔）、`exclude`（glob，逗號分隔） | `.tar.gz` |
| `mysql` | `host`、`port`、`user`、`password_env`、`databases`（空 = 全部）、`extra_args` | `.sql.gz`（`--single-transaction`，含 routines / events / triggers） |
| `postgres` | `host`、`port`、`user`、`password_env`、`database`、`extra_args` | `.dump`（`pg_dump -Fc`） |
| `mongo` | `uri_env`、`db`（空 = 全部）、`extra_args` | `.archive.gz`（`mongodump --archive --gzip`） |

共通：`enabled`、`keep_local`、`keep_remote`。

```ini
[job:mysql_main]
type=mysql
host=127.0.0.1
user=backup
password_env=MYSQL_BACKUP_PASSWORD
databases=app,auth
keep_local=3
```

- 密碼經環境變數（`MYSQL_PWD` / `PGPASSWORD`）或暫存設定檔（mongo）傳給工具，不會出現在 process 參數或 log
- 建議為備份建立唯讀帳號（MySQL 需 `SELECT, SHOW VIEW, TRIGGER, LOCK TABLES, EVENT, PROCESS`）

## 上傳

| UPLOADER | 設定 | 說明 |
|---|---|---|
| `none` | — | 只保留本機 |
| `rclone` | `RCLONE_REMOTE`；`rclone/rclone.conf` 掛載進容器 | 支援 S3、B2、GCS、Google Drive、SFTP、WebDAV… |
| `s3` | `S3_BUCKET`；`.env` 放 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | 需 `pip install boto3`（取消 `requirements.txt` 註解） |

建立 rclone 設定：

```bash
mkdir -p rclone
docker run --rm -it -v "$PWD/rclone:/config/rclone" rclone/rclone config
```

## 指令

```bash
python -m src backup                    # 全部 enabled 的 job
python -m src backup mysql_main         # 指定 job（可執行 enabled=false 的 job）
python -m src list                      # 本機與遠端備份清單
python -m src verify <備份檔>            # checksum + 壓縮檔完整性
python -m src restore <job> <備份檔> [--target X] --yes
pytest
```

還原細節見 [RESTORE.md](RESTORE.md)。

## Docker 與排程

```bash
docker compose build                                 # 需要 mongodump：INSTALL_MONGO_TOOLS=true docker compose build
docker compose run --rm backup                       # 執行全部備份
docker compose run --rm backup backup mysql_main
docker compose run --rm backup list
```

- 預設 `network_mode: host`，可直接連主機上的 `127.0.0.1` 資料庫；備份其他容器的 DB 時改加入該容器的 network
- `files` 類型需把來源路徑唯讀掛載進容器，`paths` 填容器內路徑
- 排程用主機 cron，見 [`cron/backup.cron.example`](cron/backup.cron.example)：

```cron
17 3 * * * cd /opt/backup && docker compose run --rm backup >> logs/cron.log 2>&1
```

## 擴充

| 需求 | 做法 |
|---|---|
| 新備份來源（Redis、SQLite…） | `src/sources/` 繼承 `Source`，實作 `dump()` / `restore()`、設定 `extension`，加入 `REGISTRY` |
| 新上傳目標 | `src/uploaders/` 繼承 `Uploader`，實作 `upload()` / `list()` / `delete()`，加入 `build_uploader()` |
| 新通知管道 | `src/notify/` 繼承 `Notifier`，加入 `_REGISTRY` |
| 加密 | 在 `run_job()` dump 之後加 `gpg --symmetric` / `age` 步驟，或用 rclone `crypt` remote |

## 注意事項

- `pg_dump` 版本需 ≥ PostgreSQL 伺服器版本；映像內的 `mysqldump` 為 MariaDB client，MySQL 8 專屬功能異常時改用 `mysql:8` 映像的 client
- 備份與原資料放在同一台機器不算異地備份，正式環境請設定上傳
- 定期依 [RESTORE.md](RESTORE.md#還原演練) 做還原演練
- `.env`、`conf/config.ini`、`rclone/`、`data/` 已列入 `.gitignore`
