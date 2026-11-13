"""Общие настройки тестов.

Тесты работают с настоящим PostgreSQL. Адрес тестовой базы передаётся
через переменную окружения TEST_DATABASE_URL. Перед каждым тестом все
таблицы создаются заново, после теста удаляются, поэтому база должна быть
отдельной, тестовой.
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

# --- 1. Где лежит код приложения --------------------------------------------
# В репозитории: <корень>/app/app.py, тесты в <корень>/tests.
# В Docker-образе: /code/app.py, тесты копируются в /code/tests.
ROOT = Path(__file__).resolve().parent.parent
APP_DIR = next(p for p in (ROOT / "app", ROOT) if (p / "app.py").exists())
sys.path.insert(0, str(APP_DIR))

# --- 2. Тестовая база ----------------------------------------------------------
TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    pytest.exit("Не задана переменная TEST_DATABASE_URL (адрес тестового PostgreSQL)", returncode=4)
# Защита: тесты удаляют все таблицы, поэтому имя базы обязано содержать "test"
if "test" not in (make_url(TEST_DB).database or ""):
    pytest.exit("Имя базы в TEST_DATABASE_URL должно содержать 'test' — защита рабочих данных", returncode=4)

# Заведомо фальшивые пароли для тестов. Объявлены один раз и помечены для Gitleaks,
# чтобы проверка секретов из ЛР6 не считала их утечкой.
TEST_PASSWORD = "Secret123"  # gitleaks:allow
WRONG_PASSWORD = "Wrong-000"  # gitleaks:allow

os.environ["DATABASE_URL"] = TEST_DB
os.environ["SECRET_KEY"] = "secret-for-tests-only"

from models import db

import app as app_module


@pytest.fixture(scope="session")
def flask_app():
    """Приложение Flask в режиме тестирования."""
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def clean_db(flask_app):
    """Пустая база со всеми таблицами на время одного теста."""
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(flask_app, clean_db):
    """HTTP-клиент: отправляет запросы в приложение без запуска сервера."""
    return flask_app.test_client()


# --- Помощники для интеграционных тестов ---------------------------------------
def register(client, login="ivanov", password=TEST_PASSWORD, **extra):
    form = {"login": login, "password": password, "name": "Иван", "surname": "Иванов"}
    form.update(extra)
    return client.post("/register/", data=form, follow_redirects=True)


def log_in(client, login="ivanov", password=TEST_PASSWORD):
    return client.post("/authentication/", data={"login": login, "password": password},
                       follow_redirects=True)


def create_conference(client, title="PyConf", start="2027-03-10", end="2027-03-12", **extra):
    form = {"title": title, "topic": "Python", "description": "Описание",
            "location": "Москва", "start_date": start, "end_date": end, "fee": "1000"}
    form.update(extra)
    return client.post("/conferences/new", data=form, follow_redirects=True)


@pytest.fixture
def helpers():
    """Доступ к помощникам из тестов: helpers.register(client) и т. д."""
    class H:
        pass
    H.register = staticmethod(register)
    H.log_in = staticmethod(log_in)
    H.create_conference = staticmethod(create_conference)
    return H
