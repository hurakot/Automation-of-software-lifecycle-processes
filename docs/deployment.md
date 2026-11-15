# Деплой на сервер

Пошаговый сценарий для Ubuntu Server: приложение доступно по HTTPS через nginx, PostgreSQL остаётся в сети Docker. Это инструкция для самостоятельного развёртывания; наличие работающего публичного стенда по файлам репозитория не подтверждается.

```text
Интернет → nginx :443 → 127.0.0.1:8000 → web :5000 → db :5432
                            Flask/Gunicorn          PostgreSQL 18
```

## 0. Что нужно

- Сервер Ubuntu с Docker Engine и Compose, доступом по SSH и местом для БД/бэкапов.
- Домен с DNS-записью на сервер для HTTPS.
- Исходники для сборки либо доступ к registry с готовым образом.
- Отдельные секреты для каждого стенда.

В примерах `SERVER_IP`, `example.com` и `your-account/conference-app` заменить своими значениями. STAGE и PROD в поставляемой конфигурации рассчитаны на разные ВМ.

## 1. Пользователь для работы

Создать пользователя `deploy` с sudo и настроить вход по SSH-ключу средствами сервера/хостинга. Генерация ключа на рабочей машине:

```bash
ssh-keygen -t ed25519
ssh-copy-id deploy@SERVER_IP
ssh deploy@SERVER_IP
```

## 2. SSH только по ключам

После проверки входа по ключу задать `PasswordAuthentication no` и `PermitRootLogin no` в конфигурации sshd. Проверить `sudo sshd -t`, перезагрузить конфигурацию сервиса SSH и проверить **новую сессию**, прежде чем закрывать старую. Учесть приоритет существующих drop-in-файлов образа Ubuntu.

## 3. Firewall и публикация портов

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Во всех поставляемых Compose сейчас `8000:5000`. В файле развёртывания перед запуском заменить на:

```yaml
ports:
  - "127.0.0.1:8000:5000"
```

Так nginx на хосте имеет доступ к приложению, а прямой порт не публикуется в интернет. PostgreSQL порт не публикует. Публикации Docker могут обходить правила ufw.

## 4. Docker

Установить Docker Engine и Compose для используемого образа Ubuntu. Проверить:

```bash
docker version
docker compose version
```

Пользователю `deploy` нужны права выполнять Docker-команды (через sudo либо группу docker). Членство в docker даёт привилегированный доступ к хосту; после добавления в группу требуется новая сессия.

## 5. Код на сервере

Например, скопировать исходники с рабочей машины в отдельную папку:

```bash
rsync -av --exclude .git --exclude .venv --exclude venv \
  --exclude .env --exclude volumes --exclude __pycache__ \
  --exclude .pytest_cache --exclude reports --exclude backups \
  './Conference_app (Automation)/' deploy@SERVER_IP:~/conference-app/
```

Либо использовать свой Git remote; адрес репозитория документация не предполагает. На сервере:

```bash
cd ~/conference-app
cp .env.example .env
chmod 600 .env
```

## 6. Настройки

Заполнить `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SECRET_KEY`. Секреты генерировать отдельно:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Для STAGE/PROD также указать `APP_IMAGE` и `APP_TAG`. Предпочитать тег конкретной сборки для воспроизводимого обновления и возврата на прошлый образ. Значения по умолчанию — `dev-hurakot` и `prod-hurakot` — могут быть перезаписаны в registry.

Подробности — [configuration.md](configuration.md).

## 7. Запуск из исходников

Использовать корневой `docker-compose.yaml` с исправленной привязкой порта:

```bash
cd ~/conference-app
docker compose up -d --build
docker compose ps
docker compose logs web
curl --fail http://127.0.0.1:8000/health
```

Dockerfile устанавливает runtime-зависимости, копирует содержимое `app/` в `/code`, выполняет `flask db upgrade`, затем запускает Gunicorn на 5000 с двумя workers. Код возврата миграции блокирует запуск Gunicorn при ошибке. `/health` должен вернуть `status=ok`, `database=ok`, версию образа.

## 8. STAGE/PROD из готового образа

Для стенда вместо корневого Compose разместить нужный файл в `~/conference-app/docker-compose.yaml`:

- STAGE: содержимое `deploy/stage/docker-compose.yaml`;
- PROD: содержимое `deploy/prod/docker-compose.yaml`.

Снова проверить loopback-привязку порта. Файл и `.env` находятся рядом; `./volumes/postgres` будет рядом с ними. Не переключать директорию существующей БД случайным перемещением Compose.

Образ предварительно собрать в исходном репозитории и опубликовать в своём registry:

```bash
docker build --build-arg APP_VERSION=release-42 -t your-account/conference-app:release-42 .
docker push your-account/conference-app:release-42
```

На стенде задать эти `APP_IMAGE/APP_TAG`, при необходимости выполнить `docker login`, затем:

```bash
docker compose pull
docker compose up -d
curl --fail http://127.0.0.1:8000/health
docker compose exec web flask db current
```

`APP_VERSION` встроена в образ при сборке. Тег и версия ответа должны позволять проверить, какая сборка развёрнута. Одновременный запуск нескольких стендов на одном Docker-хосте потребует изменения container_name, портов и путей данных.

## 9. nginx — доступ из интернета

Установить nginx пакетами Ubuntu. Создать `/etc/nginx/sites-available/conference-app`:

```nginx
server {
    listen 80;
    server_name example.com;
    server_tokens off;
    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включить сайт символьной ссылкой в `sites-enabled`, убедиться, что default-сайт не перехватывает домен, затем:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Заголовки передаются nginx, но приложение не настраивает `ProxyFix`: автоматическое доверие к прокси из этого примера не следует. Если оно понадобится, ограничить доверие фактическим числом прокси.

## 10. HTTPS

После настройки DNS установить Certbot с nginx-плагином и выпустить сертификат:

```bash
sudo certbot --nginx -d example.com
sudo certbot renew --dry-run
```

Проверить https://example.com и `/health`, редирект с HTTP и автопродление. Перед использованием с реальными пользователями устранить ограничения форм и cookie из [known-issues.md](known-issues.md).

Для проверки закрытого приложения до настройки домена можно использовать SSH-туннель с рабочей машины:

```bash
ssh -L 8000:127.0.0.1:8000 deploy@SERVER_IP
```

## 11. Обновление и миграции

1. Сохранить текущий тег образа, ревизию `flask db current` и резервную копию БД.
2. Проверить новую сборку и миграции на тестовой БД и STAGE.
3. Доставить код/образ, обновить конфигурацию при необходимости.
4. Для исходников выполнить `docker compose up -d --build`; для образов — `docker compose pull`, затем `docker compose up -d`.
5. Проверить логи, `/health`, текущую ревизию и пользовательские сценарии входа/создания/записи.

Миграции применяются автоматически перед запуском. При ошибке исследовать логи и состояние БД. Возврат на предыдущий образ не откатывает схему. `downgrade` может удалить данные, поэтому выполнять только после проверки совместимости и бэкапа. Изменение поля в models.py без миграции не обновляет базу.

У сервисов `restart: unless-stopped`: при включённом системном Docker они восстанавливаются после перезагрузки, если не были явно остановлены. Проверить это на стенде.

## 12. Бэкап БД и восстановление

Бэкап из директории стенда:

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump --no-owner -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/conference-before-release.sql
```

Убедиться, что команда завершилась успешно, файл непустой, и скопировать его на отдельное защищённое хранилище. Он содержит персональные данные и хэши паролей. Для последующих копий использовать уникальные имена.

Проверка восстановления — в **новую пустую отдельную базу**, например на изолированном тестовом PostgreSQL из [development.md](development.md):

```bash
docker exec conf_test_db createdb -U conf_test conference_restore_test
docker exec -i conf_test_db psql -v ON_ERROR_STOP=1 -U conf_test -d conference_restore_test < backups/conference-before-release.sql
```

После восстановления проверить таблицы, количество записей и `alembic_version`; для проверки приложением направить отдельный экземпляр на восстановленную БД. Не запускать pytest на восстановленной копии, если нужны её данные: тесты их удалят. Восстановление поверх непустой рабочей базы этим сценарием не предусмотрено.

Данные Compose — bind mount `volumes/postgres`, не именованный volume. `docker compose down` не удаляет их. Копирование работающего каталога PostgreSQL не заменяет согласованный SQL-бэкап.

## 13. Автоматизация TeamCity и инструменты БД

В этой копии есть скрипты и конфигурации проверок, но нет `.teamcity` с описанием pipeline. Следующая последовательность — схема для настройки/восстановления процесса, а не подтверждение конкретных шагов на сервере:

1. Получить исходники, установить runtime/dev-зависимости, подготовить отдельный тестовый PostgreSQL.
2. Запустить pytest с JUnit/coverage, проверки секретов Gitleaks и SQL Squawk.
3. Собрать образ с `APP_VERSION`, опубликовать под тегом сборки.
4. Сохранить бэкап и состояние схемы перед изменением стенда.
5. Обновить STAGE, проверить миграции, здоровье и сценарии.
6. Доставить проверенный образ на PROD по принятой политике, сохранить отчёты.

Секреты registry, SSH и БД хранить в защищённых параметрах CI. Автоматическое слияние веток, триггеры и разрешения нужно настраивать отдельно: их реализации в файлах нет.

Интерфейс `db/ci/dbtools.sh` (из корня checkout на агенте):

```bash
. db/ci/dbtools.sh
snapshot local
compare TEST local STAGE deploy@STAGE_IP before-release
backup deploy@PROD_IP before-release-42
export_schema local > db/schema/schema.sql
```

| Функция | Результат |
|---|---|
| `on HOST COMMAND` | Выполнение локально (`local`) либо через SSH |
| `snapshot HOST` | Нормализованный `pg_dump --schema-only` и ревизия Alembic |
| `compare NAME_A HOST_A NAME_B HOST_B LABEL` | Снимки и diff в `reports/db`; код 0 — совпали, 1 — различия, 2 — схема не получена |
| `backup HOST NAME` | SQL gzip на хосте в `~/conference-app/backups` и артефакт в `reports/backup` |
| `export_schema HOST` | SQL-снимок для `db/schema/schema.sql` |

Скрипт обращается к фиксированному контейнеру `conf_db`, реквизиты получает из его окружения. SSH требует вход по ключу без интерактивного пароля и прав Docker. Использует `StrictHostKeyChecking=accept-new`; доверенные host keys лучше подготовить заранее. На удалённых хостах предполагается Linux-окружение с используемыми утилитами.

`backup` оставляет семь последних файлов в каталоге, имя копии должно быть уникальным. Его проверка наличия `COPY` и сравнение схем не заменяют пробное восстановление. Расписание вызовов в репозитории отсутствует.

## Частые проблемы

| Симптом | Что проверить |
|---|---|
| `502 Bad Gateway` | `docker compose ps`, логи web, привязку 8000 и nginx upstream |
| web перезапускается | Ошибки `flask db upgrade`, доступность БД, DATABASE_URL и SECRET_KEY |
| Ошибка аутентификации PostgreSQL | Пароль роли в существующей БД: правка `.env` его не меняет |
| Пустой каталог после переноса | Используется ли прежний bind mount и правильная POSTGRES_DB |
| `/health` работает, страницы падают | Наличие таблиц и `flask db current`; SELECT 1 не проверяет схему |
| Конфликт `conf_db`/`conf_web` | На одном хосте уже запущен другой стенд |
| Версия `/health` осталась `local` | APP_VERSION не передан как build-arg при сборке образа |

## Проверка перед публикацией

- SSH, домен и HTTPS проверены; web слушает только loopback, БД не публикуется.
- Для стенда созданы отдельные секреты и каталог данных.
- Образ и ревизия БД проверены; бэкап восстановлен на отдельной базе.
- Учтены CSRF, валидация ролей, cookie и прочие ограничения текущей версии.
