FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RCLONE_CONFIG=/config/rclone/rclone.conf

# 備份工具：mysqldump（MariaDB client，相容 MySQL）、pg_dump、rclone
# pg_dump 版本需 ≥ 資料庫伺服器版本；不符時改用 PGDG 套件源
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-mysql-client postgresql-client rclone gzip ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# 選用：MongoDB Database Tools（mongodump / mongorestore）
# 版本與檔名請至 https://www.mongodb.com/try/download/database-tools 確認
ARG INSTALL_MONGO_TOOLS=false
ARG MONGO_TOOLS_DEB=https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-x86_64-100.10.0.deb
RUN if [ "$INSTALL_MONGO_TOOLS" = "true" ]; then \
        curl -fsSL -o /tmp/mongo-tools.deb "$MONGO_TOOLS_DEB" \
        && apt-get update && apt-get install -y --no-install-recommends /tmp/mongo-tools.deb \
        && rm -rf /tmp/mongo-tools.deb /var/lib/apt/lists/*; \
    fi

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1001 appuser \
    && mkdir -p /app/logs /app/data /config/rclone \
    && chown -R appuser:appuser /app /config
USER appuser

ENTRYPOINT ["python", "-m", "src"]
CMD ["backup"]
