# 還原步驟

```
備份檔還原與定期還原演練。還原前一律先驗證備份檔，確認目標後再執行。
```

## 目錄

- [通用流程](#通用流程)
- [files](#files)
- [mysql](#mysql)
- [postgres](#postgres)
- [mongo](#mongo)
- [從遠端取回備份](#從遠端取回備份)
- [還原演練](#還原演練)

## 通用流程

```bash
# 1. 找到要還原的備份
python -m src list mysql_main

# 2. 驗證 checksum 與壓縮檔完整性
python -m src verify data/backups/mysql_main/mysql_main_20261105-031700.sql.gz

# 3. 預覽（不加 --yes 只顯示將執行的動作）
python -m src restore mysql_main data/backups/mysql_main/mysql_main_20261105-031700.sql.gz

# 4. 確認後執行
python -m src restore mysql_main data/backups/mysql_main/mysql_main_20261105-031700.sql.gz --yes
```

Docker：

```bash
docker compose run --rm backup restore mysql_main /app/data/backups/mysql_main/<檔名> --yes
```

- 驗證失敗時會拒絕還原；確定要強制還原加 `--skip-verify`
- **建議先還原到新的資料庫 / 目錄**（`--target`），確認資料正確後再切換

## files

```bash
python -m src restore app_files <檔名>.tar.gz --target /tmp/restore --yes
```

- 必須指定 `--target`，**不會**直接覆寫原路徑
- 內容解壓到 `<target>/<原目錄名稱>/`，確認後自行搬回

手動還原：

```bash
tar -xzf <檔名>.tar.gz -C /tmp/restore
```

## mysql

```bash
# 還原到原設定的伺服器（dump 內含 CREATE DATABASE / USE）
python -m src restore mysql_main <檔名>.sql.gz --yes

# 單一資料庫還原到另一個資料庫（需先建立，且 dump 時只備份一個資料庫）
mysql -h 127.0.0.1 -u root -p -e 'CREATE DATABASE app_restore'
python -m src restore mysql_main <檔名>.sql.gz --target app_restore --yes
```

手動還原：

```bash
gzip -dc <檔名>.sql.gz | mysql -h 127.0.0.1 -u root -p
```

- 以 `--databases` / `--all-databases` 備份的 dump 含 `USE <db>`，`--target` 只對單一資料庫且無 `USE` 的 dump 有效；需還原到其他名稱時，可先用 `sed` 修改 dump 中的資料庫名稱

## postgres

```bash
# 還原到原資料庫（--clean --if-exists：先刪除既有物件）
python -m src restore pg_main <檔名>.dump --yes

# 還原到新資料庫
createdb -h 127.0.0.1 -U postgres app_restore
python -m src restore pg_main <檔名>.dump --target app_restore --yes
```

手動還原 / 檢視內容：

```bash
pg_restore -l <檔名>.dump                                   # 列出內容
pg_restore -h 127.0.0.1 -U postgres -d app_restore --clean --if-exists <檔名>.dump
```

## mongo

```bash
# 還原（--drop：先刪除同名 collection）
python -m src restore mongo_main <檔名>.archive.gz --yes

# 還原到另一個資料庫名稱（需在 job 設定 db）
python -m src restore mongo_main <檔名>.archive.gz --target app_restore --yes
```

手動還原：

```bash
mongorestore --uri "$MONGO_BACKUP_URI" --archive=<檔名>.archive.gz --gzip --drop
```

## 從遠端取回備份

```bash
# rclone
rclone copy b2:my-bucket/backups/mysql_main/<檔名> data/backups/mysql_main/
rclone copy b2:my-bucket/backups/mysql_main/<檔名>.sha256 data/backups/mysql_main/

# S3
aws s3 cp s3://my-bucket/backups/mysql_main/<檔名> data/backups/mysql_main/
aws s3 cp s3://my-bucket/backups/mysql_main/<檔名>.sha256 data/backups/mysql_main/
```

取回後同樣先執行 `verify`。

## 還原演練

沒有演練過的備份不算備份。建議每月一次：

1. 取最新備份，`verify` 通過
2. 還原到**隔離環境**的新資料庫 / 目錄（`--target`）
3. 抽查：資料表數量、關鍵資料筆數、最新資料時間
4. 紀錄耗時（作為實際災難時的 RTO 參考）與結果
