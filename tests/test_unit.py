"""Юнит-тесты: модели базы данных и отдельные функции, без HTTP-запросов."""
from datetime import date

import pytest
from conftest import TEST_PASSWORD, WRONG_PASSWORD
from models import Conference, Participation, User, db
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

import app as app_module

pytestmark = pytest.mark.unit


def make_user(login="ivanov", password=TEST_PASSWORD):
    return User(login=login, password_hash=generate_password_hash(password),
                name="Иван", surname="Иванов")


def make_conference(creator, title="PyConf"):
    return Conference(title=title, topic="Python", location="Москва",
                      start_date=date(2027, 3, 10), end_date=date(2027, 3, 12),
                      fee=1000, creator=creator)


def test_password_is_stored_as_hash(flask_app, clean_db):
    """User: в базе хранится хэш пароля, а не сам пароль, и он проверяется."""
    with flask_app.app_context():
        db.session.add(make_user())
        db.session.commit()
        user = User.query.filter_by(login="ivanov").one()
        assert user.password_hash != TEST_PASSWORD
        assert check_password_hash(user.password_hash, TEST_PASSWORD)
        assert not check_password_hash(user.password_hash, WRONG_PASSWORD)


def test_login_must_be_unique(flask_app, clean_db):
    """User: два пользователя с одним логином сохранить нельзя (unique=True)."""
    with flask_app.app_context():
        db.session.add_all([make_user("same"), make_user("same")])
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_user_cannot_join_conference_twice(flask_app, clean_db):
    """Participation: пара «пользователь — конференция» уникальна (uq_user_conference)."""
    with flask_app.app_context():
        user = make_user()
        conf = make_conference(user)
        db.session.add_all([
            Participation(role="participant", user=user, conference=conf),
            Participation(role="speaker", user=user, conference=conf),
        ])
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_conference_creator_relationship(flask_app, clean_db):
    """Conference ↔ User: связь организатора работает в обе стороны."""
    with flask_app.app_context():
        user = make_user()
        conf = make_conference(user)
        db.session.add(conf)
        db.session.commit()
        assert conf.created_by == user.id
        assert user.created_conferences == [conf]


def test_deleting_conference_deletes_participations(flask_app, clean_db):
    """Conference: каскадное удаление (cascade="all, delete-orphan") убирает записи участников."""
    with flask_app.app_context():
        user = make_user()
        conf = make_conference(user)
        db.session.add(Participation(role="organizer", user=user, conference=conf))
        db.session.commit()
        db.session.delete(conf)
        db.session.commit()
        assert Participation.query.count() == 0
        assert User.query.count() == 1  # пользователь при этом остаётся


def test_load_user(flask_app, clean_db):
    """load_user (Flask-Login): по id из сессии находит пользователя, для чужого id — None."""
    with flask_app.app_context():
        user = make_user()
        db.session.add(user)
        db.session.commit()
        assert app_module.load_user(str(user.id)).login == "ivanov"
        assert app_module.load_user("99999") is None


def test_health_reports_version(client, monkeypatch):
    """health: отвечает 200, видит базу и показывает версию из APP_VERSION."""
    monkeypatch.setenv("APP_VERSION", "dev-hurakot-42")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok", "version": "dev-hurakot-42"}
