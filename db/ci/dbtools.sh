# Инструменты для работы с БД в пайплайне TeamCity (ЛР8).
# Подключение в шаге:  . db/ci/dbtools.sh
# HOST = local (TEST-ВМ, где работает агент) или user@ip (STAGE, PROD — по SSH).

SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
# Команды выполняются ВНУТРИ контейнера conf_db: логин и имя базы берутся из его окружения
PG_SCHEMA='pg_dump --schema-only --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"'
PG_VERSION='psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select version_num from alembic_version"'
PG_BACKUP='pg_dump --no-owner -U "$POSTGRES_USER" "$POSTGRES_DB"'

# on HOST "команда" — выполнить команду на TEST-ВМ или на удалённой ВМ
on() {
  if [ "$1" = local ]; then shift; sh -c "$*"
  else h=$1; shift; ssh $SSH_OPTS "$h" "$*"; fi
}

# norm — убрать из pg_dump строки, которые меняются при каждом запуске (комментарии, \restrict)
norm() { sed -e '/^\\restrict /d' -e '/^\\unrestrict /d' -e '/^--/d' -e '/^$/d'; }

# snapshot HOST — схема БД и версия миграции Alembic
snapshot() {
  on "$1" "docker exec conf_db sh -c '$PG_SCHEMA'" | norm
  echo "alembic_version: $(on "$1" "docker exec conf_db sh -c '$PG_VERSION'")"
}

# compare ИМЯ_A HOST_A ИМЯ_B HOST_B МЕТКА — сравнить схемы, файлы в reports/db/
# код возврата: 0 — совпадают, 1 — различаются, 2 — не удалось получить схему
compare() {
  mkdir -p reports/db
  a="reports/db/$5-$1.sql"; b="reports/db/$5-$3.sql"; d="reports/db/$5-diff.txt"
  snapshot "$2" > "$a"; snapshot "$4" > "$b"
  for f in "$a" "$b"; do
    grep -q 'CREATE TABLE' "$f" || { echo "❌ Не удалось получить схему: $f"; return 2; }
  done
  echo "$1: $(tail -n 1 "$a")"
  echo "$3: $(tail -n 1 "$b")"
  if diff -u "$b" "$a" > "$d"; then
    echo "✅ Схемы БД $1 и $3 совпадают"; return 0
  fi
  echo "⚠️  Схемы БД $1 и $3 различаются (строки с - есть только на $3, с + только на $1):"
  cat "$d"; return 1
}

# backup HOST ИМЯ — резервная копия БД на сервере (~/conference-app/backups) и в артефактах сборки
backup() {
  f="conference-app/backups/$2.sql.gz"
  on "$1" "mkdir -p conference-app/backups && docker exec conf_db sh -c '$PG_BACKUP' | gzip > $f && test -s $f" \
    || { echo "❌ Не удалось сделать резервную копию"; return 1; }
  mkdir -p reports/backup
  on "$1" "cat $f" > "reports/backup/$2.sql.gz"
  n=$(gzip -dc "reports/backup/$2.sql.gz" 2>/dev/null | grep -c '^COPY ')
  [ "${n:-0}" -gt 0 ] || { echo "❌ Копия пустая или повреждена"; return 1; }
  echo "✅ Резервная копия: ~/$f ($(on "$1" "du -h $f | cut -f1"))"
  echo "   Таблиц с данными в копии: $n"
  on "$1" "ls -1t conference-app/backups/*.sql.gz | tail -n +8 | xargs -r rm --"   # хранить 7 последних
  on "$1" "ls -lh conference-app/backups"
}

# export_schema HOST — схема в виде обычного SQL для папки db/schema (без случайных строк \restrict)
export_schema() {
  on "$1" "docker exec conf_db sh -c '$PG_SCHEMA'" | sed -e '/^\\restrict /d' -e '/^\\unrestrict /d'
  echo "-- alembic_version: $(on "$1" "docker exec conf_db sh -c '$PG_VERSION'")"
}
