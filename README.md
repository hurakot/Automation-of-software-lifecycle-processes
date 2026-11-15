# Conference App

Веб-приложение для организации научных конференций: регистрация пользователей, создание мероприятий и запись участником или докладчиком.

## Идея проекта

Учебный проект по дисциплине «Автоматизация процессов жизненного цикла программных средств» (3 курс, 5 семестр). Объединяет разработку Flask-приложения и практику эксплуатации:

- регистрация и вход по логину и паролю, хранение хэшей паролей;
- каталог конференций с пагинацией и личным списком участий;
- создание конференций в очном, онлайн- и смешанном формате;
- автоматическая запись создателя организатором;
- запись участником или докладчиком с указанием темы доклада;
- миграции PostgreSQL, тесты и контейнерный запуск;
- конфигурации TEST/STAGE/PROD и инструменты для работы с БД в TeamCity.

Backend написан автором проекта. Развёртывание на ВМ Ubuntu Desktop/Server, тесты, CI/CD, перенос БД и автоматизация миграций реализованы с помощью ИИ. По исходному описанию пайплайн TeamCity использовался для обновления других веток и стендов; его серверные настройки в эту копию репозитория не входят.

## Стек технологий

| Область | Технологии |
|---|---|
| Язык | Python 3.13 (Dockerfile) |
| Веб-фреймворк | Flask 3.1, Gunicorn |
| Интерфейс | Jinja2, Bootstrap, CSS, JavaScript |
| ORM | Flask-SQLAlchemy, SQLAlchemy 2.0 |
| База данных | PostgreSQL 18, psycopg2 |
| Настройки | Переменные окружения, python-dotenv |
| Авторизация | Flask-Login, cookie-сессия Flask, Werkzeug security |
| Миграции | Flask-Migrate, Alembic |
| Тесты | pytest, pytest-cov, PostgreSQL |
| Инфраструктура | Docker Compose, Ubuntu, TeamCity, Docker Hub |
| Проверки | Конфигурации Gitleaks и Squawk |

**Деплой:** локальный Compose собирает образ из исходников. STAGE/PROD используют готовые образы `APP_IMAGE:APP_TAG`. Публичный адрес демо в проекте не указан.

## Документация

| Файл | Содержание |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Структура и назначение файлов, слои, модель данных, путь запроса, миграции |
| [docs/api.md](docs/api.md) | Все HTTP-маршруты, формы, авторизация, ответы и примеры curl |
| [docs/configuration.md](docs/configuration.md) | Переменные окружения, `.env`, секреты, порты и хранилище |
| [docs/development.md](docs/development.md) | Локальный запуск, тесты PostgreSQL, зависимости и миграции |
| [docs/deployment.md](docs/deployment.md) | VPS, STAGE/PROD, TeamCity, HTTPS, обновление и бэкапы |
| [docs/known-issues.md](docs/known-issues.md) | Ограничения текущей версии и планы улучшений |

## Быстрый старт (локально, Docker)

Нужен установленный и запущенный Docker с Compose. Из папки проекта:

```bash
cd 'Conference_app (Automation)'
cp .env.example .env
# Заполнить POSTGRES_PASSWORD и SECRET_KEY:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Выполнить дважды, использовать разные значения.
docker compose up --build
```

Открыть http://localhost:8000:

1. Зарегистрировать пользователя и войти.
2. Создать конференцию — создатель автоматически станет организатором.
3. Под другим пользователем записаться участником или докладчиком.

Проверка приложения и БД: http://localhost:8000/health. При старте контейнер сам выполняет `flask db upgrade`.

Остановить: `Ctrl+C`, затем `docker compose down`. Данные остаются в `volumes/postgres`; не удалять эту папку, если база нужна.

Запуск без Docker — в [docs/development.md](docs/development.md).

## Тесты

Требуют **отдельный PostgreSQL**: тесты удаляют и создают таблицы. Имя тестовой базы должно содержать `test`.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export TEST_DATABASE_URL='postgresql://conf_user:REPLACE_ME@localhost:5432/conference_test'
python -m pytest -q
```

Это шаблон URL: сначала создать тестовую базу и заменить реквизиты. Полный сценарий с изолированным контейнером — в [docs/development.md](docs/development.md#тесты).

## Деплой STAGE/PROD

Подготовлены два файла:

- `deploy/stage/docker-compose.yaml`: тег по умолчанию `dev-hurakot`;
- `deploy/prod/docker-compose.yaml`: тег по умолчанию `prod-hurakot`.

В отдельной директории каждого стенда разместить соответствующий файл как `docker-compose.yaml`, создать `.env` и указать `APP_IMAGE`, `APP_TAG`, `POSTGRES_*`, `SECRET_KEY`.

```bash
docker compose pull
docker compose up -d
curl --fail http://127.0.0.1:8000/health
```

Стенды рассчитаны на отдельные ВМ: у контейнеров фиксированные имена и одинаковый порт. Пошаговый сценарий, требования к образу и CI/CD — в [docs/deployment.md](docs/deployment.md).

## Запуск на собственном сервере (VPS)

Можно собирать исходники корневым Compose либо использовать готовый образ. Для доступа по домену nginx проксирует запросы к `127.0.0.1:8000`, HTTPS завершает на сервере.

**Перед публикацией:** в используемом Compose заменить `8000:5000` на `127.0.0.1:8000:5000`. В поставляемых файлах порт 8000 доступен на всех интерфейсах.

Подготовка Ubuntu, настройка nginx, HTTPS, бэкап и восстановление — в [docs/deployment.md](docs/deployment.md).

## Безопасность

- Пароли хранятся как хэши Werkzeug, вход поддерживает Flask-Login.
- `.env` и данные PostgreSQL исключены из Git и Docker-контекста; шаблон `.env.example` не содержит рабочих секретов.
- PostgreSQL в Compose не публикует порт на хосте.
- В текущей версии нет CSRF-защиты и ограничения попыток входа; контейнер приложения работает от root. Подробности — в [docs/known-issues.md](docs/known-issues.md).
