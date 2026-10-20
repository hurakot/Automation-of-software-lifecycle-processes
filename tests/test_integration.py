"""Интеграционные тесты: HTTP-запросы проходят через Flask, Flask-Login,
SQLAlchemy и настоящий PostgreSQL — проверяется совместная работа модулей."""
import re

import pytest
from conftest import TEST_PASSWORD, WRONG_PASSWORD
from models import Conference, Participation, User

pytestmark = pytest.mark.integration

# Заголовки карточек конференций в основном списке главной страницы
CARD_TITLES = re.compile(r'card-title mb-1">([^<]+)</h2>')


# ---------- Регистрация и вход ----------

def test_register_creates_user(client, helpers, flask_app):
    page = helpers.register(client, login="petrov")
    assert "Успешно создана новая запись" in page.get_data(as_text=True)
    with flask_app.app_context():
        user = User.query.filter_by(login="petrov").one()
        assert user.name == "Иван" and user.password_hash != TEST_PASSWORD


def test_register_rejects_taken_login(client, helpers, flask_app):
    helpers.register(client, login="petrov")
    page = helpers.register(client, login="petrov")
    assert "логин уже занят" in page.get_data(as_text=True)
    with flask_app.app_context():
        assert User.query.filter_by(login="petrov").count() == 1


def test_login_with_correct_password(client, helpers):
    helpers.register(client)
    page = helpers.log_in(client)
    assert "Вы успешно зашли на сайт" in page.get_data(as_text=True)


def test_login_with_wrong_password(client, helpers):
    helpers.register(client)
    page = helpers.log_in(client, password=WRONG_PASSWORD)
    assert "неправильно ввели данные" in page.get_data(as_text=True)
    # без входа защищённая страница недоступна
    assert client.get("/conferences/new").status_code == 302


def test_protected_page_requires_login(client):
    response = client.get("/conferences/new")
    assert response.status_code == 302
    assert "/authentication/" in response.headers["Location"]


def test_logout(client, helpers):
    helpers.register(client)
    helpers.log_in(client)
    assert client.get("/conferences/new").status_code == 200
    client.post("/goout", follow_redirects=True)
    assert client.get("/conferences/new").status_code == 302


# ---------- Конференции ----------

def test_create_conference_makes_user_organizer(client, helpers, flask_app):
    helpers.register(client)
    helpers.log_in(client)
    page = helpers.create_conference(client, title="PyConf 2027").get_data(as_text=True)
    assert "PyConf 2027" in page
    assert "Вы — организатор конференции" in page
    with flask_app.app_context():
        conf = Conference.query.filter_by(title="PyConf 2027").one()
        roles = [p.role for p in conf.participations]
        assert roles == ["organizer"]
        assert conf.creator.login == "ivanov"


def test_conference_title_must_be_unique(client, helpers, flask_app):
    helpers.register(client)
    helpers.log_in(client)
    helpers.create_conference(client, title="PyConf")
    page = helpers.create_conference(client, title="PyConf")
    assert "уже существует" in page.get_data(as_text=True)
    with flask_app.app_context():
        assert Conference.query.filter_by(title="PyConf").count() == 1


def test_main_page_newest_first_two_per_page(client, helpers):
    helpers.register(client)
    helpers.log_in(client)
    helpers.create_conference(client, title="Старая", start="2027-01-10", end="2027-01-11")
    helpers.create_conference(client, title="Средняя", start="2027-02-10", end="2027-02-11")
    helpers.create_conference(client, title="Новая", start="2027-03-10", end="2027-03-11")
    page1 = client.get("/").get_data(as_text=True)
    page2 = client.get("/?page=2").get_data(as_text=True)
    assert CARD_TITLES.findall(page1) == ["Новая", "Средняя"]  # сначала самые поздние
    assert CARD_TITLES.findall(page2) == ["Старая"]


def test_conference_page_shows_participants_count(client, helpers):
    helpers.register(client, login="org")
    helpers.log_in(client, login="org")
    helpers.create_conference(client, title="PyConf")
    client.post("/goout")
    helpers.register(client, login="guest")
    helpers.log_in(client, login="guest")
    client.post("/conferences/1/join", data={"role": "participant"})
    page = client.get("/conferences/1/").get_data(as_text=True)
    count = page.split("Записалось")[1].split("</dd>")[0]
    assert count.strip().endswith("1")


# ---------- Запись на конференцию ----------

@pytest.fixture
def conference_and_guest(client, helpers):
    """Конференцию создаёт org, затем входит другой пользователь guest."""
    helpers.register(client, login="org")
    helpers.log_in(client, login="org")
    helpers.create_conference(client, title="PyConf")
    client.post("/goout")
    helpers.register(client, login="guest")
    helpers.log_in(client, login="guest")
    return client


def test_join_as_participant(conference_and_guest, flask_app):
    page = conference_and_guest.post("/conferences/1/join", data={"role": "participant"},
                                     follow_redirects=True)
    assert "Вы успешно записались" in page.get_data(as_text=True)
    with flask_app.app_context():
        p = Participation.query.filter_by(role="participant").one()
        assert p.user.login == "guest" and p.report_topic is None


def test_join_as_speaker_saves_report_topic(conference_and_guest, flask_app):
    conference_and_guest.post("/conferences/1/join",
                              data={"role": "speaker", "report_topic": "Тесты в CI"})
    with flask_app.app_context():
        p = Participation.query.filter_by(role="speaker").one()
        assert p.report_topic == "Тесты в CI"


def test_cannot_join_twice(conference_and_guest, flask_app):
    conference_and_guest.post("/conferences/1/join", data={"role": "participant"})
    page = conference_and_guest.post("/conferences/1/join", data={"role": "participant"},
                                     follow_redirects=True)
    assert "Вы уже записаны" in page.get_data(as_text=True)
    with flask_app.app_context():
        assert Participation.query.filter_by(role="participant").count() == 1


def test_organizer_cannot_join_own_conference(client, helpers):
    helpers.register(client)
    helpers.log_in(client)
    helpers.create_conference(client)
    page = client.get("/conferences/1/join", follow_redirects=True)
    assert "Вы — организатор этой конференции" in page.get_data(as_text=True)


def test_join_missing_conference(client, helpers):
    helpers.register(client)
    helpers.log_in(client)
    page = client.get("/conferences/999/join", follow_redirects=True)
    assert "Такой конференции не существует" in page.get_data(as_text=True)


# ---------- Миграции ----------

def test_migrations_create_all_tables(flask_app, clean_db):
    """Миграции Alembic (flask db upgrade) на пустой базе создают все таблицы."""
    from pathlib import Path

    from flask_migrate import downgrade, upgrade
    from models import db
    from sqlalchemy import inspect

    import app as app_module

    migrations = Path(app_module.__file__).parent / "migrations"
    with flask_app.app_context():
        db.drop_all()
        upgrade(directory=str(migrations))
        tables = set(inspect(db.engine).get_table_names())
        assert {"users", "conferences", "participations", "alembic_version"} <= tables
        downgrade(directory=str(migrations), revision="base")
