import random
import sqlite3
from flask import Flask, render_template, g, request, session, redirect, url_for, flash, get_flashed_messages
from flask import Flask, make_response, render_template_string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from faker import Faker
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
from datetime import datetime, timedelta
from functools import wraps
from models import db, User, Participation, Conference

from flask_migrate import Migrate

from dotenv import load_dotenv

import os
import base64
import json

# Загружаем переменные из .env (при запуске и через `flask run`, и через `python app.py`)
load_dotenv()
 
app = Flask(__name__)
 
# Все настройки подключения берутся из окружения, в коде нет localhost и паролей.
# В Docker поменяется только значение DATABASE_URL.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
 
# Связываем SQLAlchemy с приложением: db узнаёт, к какой БД подключаться
db.init_app(app)
 
# Миграции: команды `flask db init / migrate / upgrade`
migrate = Migrate(app, db)
 
# Flask-Login: хранит id пользователя в сессии и достаёт его из БД
login_manager = LoginManager(app)
login_manager.login_view = "authentication"  # имя view-функции страницы входа (создашь позже)
 
#Сообщение, появляющееся, если вы не прошли авторизацию
@login_manager.unauthorized_handler
def unauthorized():
    flash("Пройдите процедуру авторизации, чтобы получить доступ к странице.", "danger")
    return redirect(url_for('authentication'))




# <-- Функция logout - Выход из системы -->
@app.route('/goout', methods=['GET', 'POST'])
@login_required
def goout():
    if request.method == 'POST':
        logout_user()
        flash("Вы вышли из системы, повторно пройдите автоизацию!", "success")
        return redirect(url_for('main_page'))
    return redirect(url_for('main_page'))



# Загрузка пользователя, если он проходил авторизацию
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# <!-- Аутентификация -->

# <!-- authentication.html - Страница авторизации в систему -->
@app.route('/authentication/', methods=['GET', 'POST'])
def authentication():
    if request.method == "POST":
        login = request.form.get('login')
        password = request.form.get('password')
        userdata = User.query.filter_by(login=login).first()
        if (userdata and check_password_hash(userdata.password_hash, password)):
            login_user(userdata)
            flash(f"Вы успешно зашли на сайт!", "success")
            return redirect(url_for('main_page'))
        else:
            flash(f"Вы неправильно ввели данные, попробуйте ещё раз.", "danger")
            return redirect(url_for('authentication'))
    return render_template('authentication.html')

# <!-- register.html - Страница регистрации (создания) пользователя для системы -->
@app.route('/register/', methods=['GET', 'POST'])
def register():
    now = datetime.now().date()
    if request.method == "POST":
        login = request.form.get('login')
        password = request.form.get('password')
        name = request.form.get('name')
        surname = request.form.get('surname')
        patronymic = request.form.get('patronymic')
        academic_degree = request.form.get('academic_degree')
        workplace = request.form.get('workplace')
        position = request.form.get('position')
        research_field = request.form.get('research_field')
        phone = request.form.get('phone')
        created_at = now
        userdata = User.query.filter_by(login=login).first()
        if not userdata:
            try:
                new_user = User(
                    login = login,
                    password_hash = generate_password_hash(password),
                    name = name,
                    surname=surname,
                    patronymic=patronymic,
                    academic_degree=academic_degree,
                    workplace=workplace,
                    position=position,
                    research_field=research_field,
                    phone=phone,
                    created_at=created_at
                )
                db.session.add(new_user)
                db.session.commit() 
                flash("Успешно создана новая запись", "success")
                return redirect(url_for('authentication'))
            except Exception as e:
                flash("Ошибка:" + str(e), "danger")
                db.session.rollback()
        else:
            flash("Введённый логин уже занят, введите другой логин.", "danger")


    return render_template('register.html')

# <!-- main_page.html - Главная страница сайта -->
@app.route("/", methods=['GET'])
def main_page():
    signed_conferences = [] # Пустая, на случай, если пользователь - неавторизованный.
    page = request.args.get('page', 1, type=int)
    pagination = (Conference.query.order_by(Conference.start_date.desc())).paginate(
        page=page,
        per_page=2,
        error_out=False
    )   
    conferences = pagination.items
    # Используем current_user
    if current_user.is_authenticated:
        signed_conferences = Participation.query.filter_by(user_id = current_user.id).all() # Конференции, на которые подписался участник.
    return render_template('main_page.html', conferences=conferences, pagination=pagination, signed_conferences=signed_conferences)



# <!-- conferences_new.html - Страница создания конференции -->
@app.route('/conferences/new', methods=['GET', 'POST'])
@login_required
def conference_new():
    now = datetime.now().date()
    if request.method == "POST":
        title = request.form.get('title')
        topic = request.form.get('topic')
        description = request.form.get('description')
        location = request.form.get('location')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        fee = request.form.get('fee')

        userdata = Conference.query.filter_by(title=title).first()
        if not userdata:
            try:
                new_conference = Conference(
                    title = title,
                    topic = topic,
                    description = description,
                    location = location,
                    start_date = start_date,
                    end_date = end_date,
                    fee = fee,
                    created_by = current_user.id,
                    created_at = now,
                    creator = current_user
                )
                new_participation = Participation(
                    role = "organizer",
                    registered_at = now,
                    user_id = current_user.id,
                    conference = new_conference
                )
                db.session.add_all([new_conference, new_participation])
                db.session.commit() 
                flash("Успешно создана новая конференция. Теперь вы её новый организатор и пожалуйста отслеживайте её.", "success")
                return redirect(url_for('conference_full_page', id_conference = new_conference.id))
            except Exception as e:
                flash("Ошибка:" + str(e), "danger")
                db.session.rollback()
        else:
            flash("Конференция под таким названием уже существует, попробуйте создать другую конференцию.", "danger")
    
    
    return render_template('conferences_new.html')



# <!-- conferences_full_page.html - Страница с полной информацией о конференции -->
@app.route('/conferences/<int:id_conference>/', methods=['GET'])
@login_required
def conference_full_page(id_conference):
    
    conference=Conference.query.get(id_conference)
    if not conference:
        return redirect(url_for('main_page'))
    participation = Participation.query.filter_by(user_id=current_user.id, conference_id=id_conference).first() # Чувак участвует или нет?
    return render_template('conferences_full_page.html', conference=conference, participation=participation)

# <!-- conferences_join.html - Страница с присоединением к конференции в качестве участника или в качестве докладчика -->
@app.route('/conferences/<int:id_conference>/join', methods=['GET', 'POST'])
@login_required
def conference_join(id_conference):
    now = datetime.now().date()

    # 1. Конференция должна существовать
    conference = db.session.get(Conference, id_conference)
    if not conference:
        flash("Такой конференции не существует.", "danger")
        return redirect(url_for('main_page'))

    # 2. Пользователь не должен быть уже записан (в том числе как организатор)
    participation = Participation.query.filter_by(
        user_id=current_user.id, conference_id=id_conference
    ).first()
    if participation:
        if participation.role == "organizer":
            flash("Вы — организатор этой конференции.", "danger")
        else:
            flash("Вы уже записаны на эту конференцию.", "danger")
        return redirect(url_for('conference_full_page', id_conference=id_conference))

    if request.method == "POST":
        role = request.form.get('role')
        if role == "speaker":
            report_topic = request.form.get('report_topic')
        else:
            report_topic = None
        try:
            new_participation = Participation(
                role=role,
                report_topic=report_topic,
                registered_at=now,
                user_id=current_user.id,
                conference=conference
            )
            db.session.add(new_participation)
            db.session.commit()
            flash("Вы успешно записались на конференцию.", "success")
            return redirect(url_for('main_page'))
        except Exception as e:
            flash("Ошибка:" + str(e), "danger")
            db.session.rollback()

    return render_template('conferences_join.html', conference=conference)

# <!-- не нужен html - Проверка работоспособности системы и то, что работает БД -->
@app.route("/health")
def health():
    """Проверка, что приложение живо и БД отвечает. Пригодится для Docker и CI."""
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok", "version": os.environ.get("APP_VERSION", "local")}
    except Exception as e:
        return {"status": "error", "database": str(e)}, 500

if __name__ == "__main__":
    # Порт 5001, потому что на macOS порт 5000 занят AirPlay Receiver
    # Отладчик включается только явно: FLASK_DEBUG=1 python app.py
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5001)
