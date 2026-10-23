# Актуальная схема базы данных

`schema.sql` — снимок схемы PostgreSQL, выгруженный штатным средством СУБД
(`pg_dump --schema-only`) с TEST-стенда после применения всех миграций.

Как обновить (на TEST-ВМ, из корня репозитория):

    . db/ci/dbtools.sh
    export_schema local > db/schema/schema.sql

Файл не выполняется: схему на стендах меняют миграции Alembic из `app/migrations/versions`.
Снимок нужен, чтобы в Git и в PR было видно, как меняется структура БД.
