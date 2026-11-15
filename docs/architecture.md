# Архитектура

## Структура проекта

```text
Conference_app (Automation)/
├── app/
│   ├── app.py                  # настройки, Flask, HTTP-обработчики, /health
│   ├── models.py               # db, User, Conference, Participation
│   ├── templates/
│   │   ├── base.html           # общий каркас, меню, flash-сообщения
│   │   ├── main_page.html      # каталог, пагинация, личные участия
│   │   ├── authentication.html # форма входа
│   │   ├── register.html       # регистрация и профиль
│   │   ├── conferences_new.html       # создание конференции
│   │   ├── conferences_full_page.html # сведения и статус участия
│   │   └── conferences_join.html      # роль и тема доклада
│   ├── static/
│   │   ├── css/bootstrap.min.css # поставляемые стили Bootstrap
│   │   ├── css/style.css         # собственные стили
│   │   └── js/bootstrap.bundle.min.js # компоненты Bootstrap
│   └── migrations/
│       ├── README              # служебное описание Alembic
│       ├── alembic.ini         # настройки логирования Alembic
│       ├── env.py              # связь миграций с Flask-SQLAlchemy
│       ├── script.py.mako      # шаблон новой ревизии
│       └── versions/
│           ├── 7d643ecb0fe6_initial.py # исходные таблицы
│           ├── b3f1c2d4e5a6_conference_format.py # формат мероприятия
│           └── c7d8e9f0a1b2_conferences_start_date_index.py # индекс даты
├── tests/
│   ├── conftest.py             # тестовая БД, фикстуры, помощники
│   ├── test_unit.py            # модели, хэши, связи, /health
│   └── test_integration.py     # HTTP-сценарии и миграции
├── db/
│   ├── ci/dbtools.sh           # сравнение схем, бэкапы, экспорт
│   ├── manual/002_conference_format.sql # SQL для одного перехода схемы
│   └── schema/
│       ├── README.md           # как обновлять снимок
│       └── schema.sql          # снимок структуры PostgreSQL
├── deploy/
│   ├── stage/docker-compose.yaml # готовый образ, dev-hurakot
│   └── prod/docker-compose.yaml  # готовый образ, prod-hurakot
├── docs/                       # шесть тематических документов
├── Dockerfile                  # Python, миграции, Gunicorn
├── docker-compose.yaml         # локальная сборка web + PostgreSQL 18
├── requirements.txt            # зависимости приложения
├── requirements-dev.txt        # pytest и pytest-cov; runtime не включает
├── pytest.ini                  # каталог тестов, маркеры unit/integration
├── .env.example                # шаблон настроек
├── .gitignore                  # исключения Git
├── .dockerignore               # исключения Docker-контекста
├── .gitleaks.toml              # проверка секретов, в том числе URL БД
├── .squawk.toml                # правила проверки SQL для PostgreSQL 18
├── 1.py                        # отдельный print("hi"), не часть приложения
├── hello.py                    # отдельный Hello World
├── good.txt                    # дополнительный список пакетов; сборка не читает
└── README.md                   # обзор и быстрый старт
```

Локально могут присутствовать `.env`, виртуальное окружение, `volumes/` и исходный `README Ориг с git in automation.txt`; это не исполняемые модули приложения. Содержимое секретного `.env` документация не воспроизводит.

## Слои и их ответственность

| Слой | Файлы | Что делает |
|---|---|---|
| Точка входа и настройки | `app/app.py` | Загружает dotenv, создаёт Flask, подключает db, Migrate и LoginManager |
| HTTP и бизнес-операции | `app/app.py` | Читает формы, проверяет вход и дубли, выполняет транзакции, возвращает HTML/redirect |
| Модели и доступ к БД | `app/models.py` | Описывает таблицы, ограничения и отношения ORM |
| Представление | `app/templates/`, `app/static/` | Серверный HTML, формы и оформление |
| Изменение схемы | `app/migrations/` | Версионирует структуру БД через Alembic |
| Проверки | `tests/` | Проверяет модели и HTTP на настоящем PostgreSQL |
| Эксплуатация | Compose, Dockerfile, `db/ci/` | Запуск, доставка образов и операции с БД |

Это синхронный монолит с серверным рендерингом. Отдельных service/repository-слоёв, REST JSON API, JWT и фабрики `create_app` сейчас нет. Конфигурация читается при импорте модуля.

## Модель данных

| Таблица | Поля и ограничения |
|---|---|
| `users` | `id` PK; `login` TEXT UNIQUE NOT NULL; `password_hash`, `name`, `surname` TEXT NOT NULL; необязательные `patronymic`, `academic_degree`, `workplace`, `position`, `research_field`, `phone`; `created_at` DATE |
| `conferences` | `id` PK; `title`, `topic`, `location` TEXT NOT NULL; `description` TEXT nullable; `start_date`, `end_date` DATE NOT NULL; `fee` INTEGER NOT NULL; `format` TEXT NOT NULL DEFAULT offline; `created_by` FK → users.id NOT NULL; `created_at` DATE |
| `participations` | `id` PK; `role` TEXT NOT NULL; `report_topic` TEXT nullable; `registered_at` DATE; `user_id` FK → users.id NOT NULL; `conference_id` FK → conferences.id NOT NULL; UNIQUE(user_id, conference_id) |

Даты создания имеют серверный default `now()`; HTTP-обработчики также передают текущую локальную дату. Индекс `ix_conferences_start_date` ускоряет сортировку каталога.

```text
users 1 ───── N conferences   (created_by — создатель)
users 1 ───── N participations N ───── 1 conferences
```

Участие связывает пользователя и конференцию с ролью `organizer`, `speaker` или `participant`. Роль относится к конкретной конференции. Создатель записывается организатором той же транзакцией.

ORM-отношения: `User.participations` ↔ `Participation.user`, `User.created_conferences` ↔ `Conference.creator`, `Conference.participations` ↔ `Participation.conference`. Для участий пользователя и конференции задан `cascade="all, delete-orphan"`. Это каскад SQLAlchemy, не `ON DELETE CASCADE` в PostgreSQL. Удаление конференций через HTTP не реализовано.

## Как проходит запрос

Пример: `POST /conferences/1/join`.

1. Gunicorn передаёт запрос Flask; Flask восстанавливает подписанную cookie-сессию.
2. Flask-Login вызывает `load_user`, который получает `User` по id через `db.session.get`.
3. `login_required` отправляет гостя на `/authentication/` с flash-сообщением.
4. Обработчик проверяет наличие конференции и существующего участия.
5. Из формы берёт роль, а для `speaker` — тему доклада; сохраняет `Participation` и делает `commit`.
6. При успехе добавляет flash-сообщение и возвращает `302` на главную. При ошибке откатывает транзакцию и снова показывает форму.

`db.session` привязана к контексту Flask и очищается расширением при завершении контекста. Отдельного асинхронного движка нет.

## Доступ к данным

Главная доступна гостям, подробности конференции и запись требуют входа. Авторизованный пользователь может создавать конференции и смотреть подробности любой существующей конференции. Главная сортируется по `start_date DESC`, по две записи на страницу; это сортировка по дате мероприятия, а не по дате создания.

Повторное участие запрещено и обработчиком, и ограничением БД. Уникальность названия проверяется только запросом в обработчике: UNIQUE на `conferences.title` отсутствует. Допустимые роли и форматы не ограничены CHECK в БД.

## Создание и изменение таблиц

Цепочка ревизий:

```text
base → 7d643ecb0fe6 → b3f1c2d4e5a6 → c7d8e9f0a1b2 (head)
```

Первая создаёт три таблицы, вторая добавляет `format` с default для старых строк, третья создаёт индекс `CONCURRENTLY` в `autocommit_block` вне обычной транзакции. Docker запускает миграции перед двумя worker-процессами Gunicorn; при ошибке миграции сервер не запускается.

`db/schema/schema.sql` — снимок для сравнения, не сценарий установки. Ручной SQL переводит только первую ревизию во вторую и меняет `alembic_version`; одновременно с обычным upgrade его не применять. Порядок работы — в [development.md](development.md).
