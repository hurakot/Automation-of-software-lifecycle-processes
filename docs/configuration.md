# Конфигурация

Настройки читаются в `app/app.py`: сначала `load_dotenv()`, затем `os.environ`. Уже заданные переменные окружения имеют приоритет над `.env`. `DATABASE_URL` и `SECRET_KEY` обязательны: отсутствие вызывает ошибку при импорте. Непустота ключа отдельно не проверяется.

```bash
cp .env.example .env
chmod 600 .env
```

## Переменные

| Переменная | Кто использует | Пример / default | Описание |
|---|---|---|---|
| `POSTGRES_USER` | Compose, PostgreSQL | `conf_user` в шаблоне | Пользователь БД |
| `POSTGRES_PASSWORD` | Compose, PostgreSQL | заменить `REPLACE_ME` | Секрет, задаётся при инициализации кластера |
| `POSTGRES_DB` | Compose, PostgreSQL | `conference` в шаблоне | Имя базы |
| `DATABASE_URL` | Flask-SQLAlchemy | `postgresql://USER:PASSWORD@HOST:5432/DB` | Синхронное подключение psycopg2 |
| `SECRET_KEY` | Flask | обязательна | Секрет подписи cookie-сессий и flash-сообщений |
| `TEST_DATABASE_URL` | `tests/conftest.py` | без default | Отдельная PostgreSQL, имя базы содержит `test` |
| `APP_IMAGE` | Compose STAGE/PROD | без default | Репозиторий готового образа |
| `APP_TAG` | Compose STAGE/PROD | stage: `dev-hurakot`; prod: `prod-hurakot` | Тег образа |
| `APP_VERSION` | Docker build ARG и `/health` | `local` | Версия сборки |
| `FLASK_DEBUG` | прямой запуск `python app.py` | debug только при `1` | Отладка для разработки |

`requirements-dev.txt` не подключает runtime-зависимости: устанавливать оба requirements-файла.

## DATABASE_URL: локально и в Docker

- При запуске из `app/` dotenv может найти `.env` в корне проекта. Хост в URL должен быть доступен с машины, где запущен Python.
- В Compose URL составляется из `POSTGRES_*`, хост — `db`. Переданный контейнеру URL перекрывает значение из `.env`.
- Корневой Compose не публикует PostgreSQL на хосте: одного `DATABASE_URL=...localhost...` для доступа из venv недостаточно. Нужна отдельная локальная БД или тестовый контейнер с опубликованным портом.
- Пароль с `@`, `:`, `/` требует URL-кодирования. Для текущего шаблона Compose проще использовать URL-safe секрет.

## Генерация секретов

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Сгенерировать отдельно пароль БД и `SECRET_KEY`. Для каждого стенда использовать свои значения. Смена `SECRET_KEY` делает старые сессии недействительными. Изменение `POSTGRES_PASSWORD` в `.env` не меняет пароль уже инициализированного PostgreSQL: нужна согласованная смена роли в БД и настройки приложения.

`.env` исключён из Git и Docker-контекста. Не помещать рабочие секреты в `.env.example`, команды сборки, SQL-снимки и отчёты CI.

## Порты и хранилище

| Запуск | Адрес |
|---|---|
| `python app.py` из `app/` | `http://127.0.0.1:5001` |
| Gunicorn в контейнере | `0.0.0.0:5000` |
| Все поставляемые Compose | хост `8000` → контейнер `5000`, все интерфейсы хоста |
| PostgreSQL в сети Compose | `db:5432`, без публикации на хост |

PostgreSQL 18 хранит данные в bind mount `./volumes/postgres:/var/lib/postgresql`. Относительный путь считается от директории Compose-файла. При копировании файла на стенд данные окажутся рядом с новой копией. `docker compose down` сохраняет каталог; `down -v` также не удаляет этот bind mount, но может удалять иные управляемые volumes. Не удалять `volumes/postgres` без резервной копии.

У сервисов заданы `conf_db` и `conf_web`: `-p` не устраняет конфликт имён между несколькими стендами на одном Docker-хосте.

## Версия сборки

```bash
docker compose build --build-arg APP_VERSION=release-42 web
docker compose up -d
curl --fail http://localhost:8000/health
```

В STAGE/PROD версия должна быть встроена при сборке готового образа. Compose этих стендов не передаёт `APP_VERSION` в runtime; добавление значения только в `.env` не изменит ответ `/health`.
