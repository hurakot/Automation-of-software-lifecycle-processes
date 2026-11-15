# Разработка и тесты

## Локальный запуск без Docker

Нужны Python 3.13 и доступный PostgreSQL с отдельной базой приложения.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
# Заполнить DATABASE_URL и SECRET_KEY в .env.
cd app
python -m flask --app app db upgrade
python app.py
```

Открыть http://127.0.0.1:5001. Порт 5001 выбран, чтобы избежать конфликта с AirPlay на macOS. Для отладки: `FLASK_DEBUG=1 python app.py`. В production используется Gunicorn из Dockerfile.

Команды Flask выполнять из `app/`: модуль использует `from models import ...`, а каталог миграций расположен рядом с `app.py`.

## Локальный запуск в Docker

Из корня проекта:

```bash
cp .env.example .env
# Заполнить POSTGRES_PASSWORD и SECRET_KEY.
docker compose up --build
```

Открыть http://localhost:8000. Сначала Compose ждёт PostgreSQL healthcheck, затем контейнер приложения выполняет миграции и запускает два worker-процесса Gunicorn. `.env` в образ не копируется, настройки приходят из Compose.

## Тесты

Тесты используют настоящий PostgreSQL, включая миграцию индекса `CONCURRENTLY`. SQLite не заменяет этот сценарий. Даже группа `unit` требует подключения к PostgreSQL.

Безопасный отдельный контейнер (порт `55432`, собственное имя):

```bash
docker run -d --name conf_test_db \
  -e POSTGRES_USER=conf_test \
  -e POSTGRES_PASSWORD=local-test-only \
  -e POSTGRES_DB=conference_test \
  -p 127.0.0.1:55432:5432 postgres:18

docker exec conf_test_db pg_isready -U conf_test -d conference_test
```

Дождаться `accepting connections`, затем в активном venv из корня проекта:

```bash
export TEST_DATABASE_URL='postgresql://conf_test:local-test-only@127.0.0.1:55432/conference_test'
python -m pytest -q
python -m pytest -m unit -q
python -m pytest -m integration -q
python -m pytest --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml --junitxml=pytest-results.xml
```

Тестовый пароль выше предназначен только для локальной изолированной базы.

- `conftest.py` требует `TEST_DATABASE_URL` и проверяет наличие `test` в имени базы. При отсутствии/неподходящем имени pytest завершается с кодом `4`.
- Перед импортом приложения подменяет `DATABASE_URL` и `SECRET_KEY`, добавляет каталог приложения в `sys.path`.
- `clean_db` вызывает `drop_all/create_all` перед тестом и удаляет таблицы после него. Проверка имени — дополнительный барьер, а не разрешение использовать рабочую БД с `test` в названии.
- `client` — Flask test client: HTTP-сервер и Gunicorn не запускаются.
- Unit-проверки покрывают хэши, уникальность логина и участия, связи, ORM-каскад, загрузку пользователя и `/health`.
- Интеграционные — регистрацию, вход/выход, защиту страниц, создание, формат конференции, сортировку/пагинацию, счётчик участников, запись и цепочку миграций.
- Тест миграций выполняет upgrade и downgrade до `base`. Для него нужна чистая тестовая БД без старого состояния `alembic_version`.

Остановить тестовую БД: `docker stop conf_test_db`; возобновить: `docker start conf_test_db`. Не запускать тесты параллельно на одной базе: они пересоздают общие таблицы.

## Зависимости

| Файл | Назначение |
|---|---|
| `requirements.txt` | Runtime-пакеты, устанавливаются Dockerfile |
| `requirements-dev.txt` | Только pytest и pytest-cov; устанавливается вместе с runtime |
| `good.txt` | Дополнительный список, не источник зависимостей сборки |

При добавлении пакета указать проверенную версию в соответствующем requirements-файле, установить зависимости и прогнать относящиеся к изменению тесты. Не заменять runtime-список полной выгрузкой случайного venv.

## Миграции БД

Из `app/` с настроенным окружением:

```bash
python -m flask --app app db current
python -m flask --app app db history
# После изменения models.py:
python -m flask --app app db migrate -m 'describe change'
# Проверить сгенерированные upgrade/downgrade вручную.
python -m flask --app app db upgrade
```

Не выполнять `db init`: каталог миграций уже существует. Автогенерация не заменяет проверку SQL, потери данных и блокировок. Прогнать миграцию на тестовой БД, затем на STAGE. `downgrade` может удалять данные; на PROD сначала бэкап и оценка совместимости старого приложения.

Экспорт SQL для проверки Squawk (из `app/`):

```bash
python -m flask --app app db upgrade --sql > /tmp/conference-migrations.sql
```

Конфигурация `.squawk.toml` находится в корне; сканер и Gitleaks устанавливаются отдельно, requirements их не содержат. Конкретные команды их запуска в TeamCity в репозитории не сохранены.

После миграций обновить снимок схемы из корня на хосте с контейнером `conf_db`:

```bash
. db/ci/dbtools.sh
export_schema local > db/schema/schema.sql
```

Проверить результат перед коммитом. Описание снимка — [../db/schema/README.md](../db/schema/README.md). Снимок и `db/manual/002_conference_format.sql` не использовать вместо миграций на новой базе.

## Полезные команды Docker

| Команда | Что делает |
|---|---|
| `docker compose up -d --build` | Локальная сборка и запуск |
| `docker compose logs -f web` | Миграции и логи Gunicorn |
| `docker compose logs db` | Логи PostgreSQL |
| `docker compose ps` | Статусы сервисов |
| `docker compose down` | Остановить и удалить контейнеры, сохранить bind mount |
| `docker compose exec web flask db current` | Текущая ревизия БД |
| `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'` | Консоль PostgreSQL |

В образ не копируются `tests/` и dev-зависимости: Dockerfile переносит только `app/` в `/code`. Для CI тесты запускать в отдельном подготовленном окружении либо явно добавлять их в тестовый образ.
