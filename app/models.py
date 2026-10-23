from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# ---------- Таблица пользователей ----------
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True) # id
    login = db.Column(db.Text, unique=True, nullable=False) # Логин
    password_hash = db.Column(db.Text, nullable=False) # Хэш от пароля
    name = db.Column(db.Text, nullable=False) # Имя
    surname = db.Column(db.Text, nullable=False) # Фамилия
    patronymic = db.Column(db.Text, nullable=True) # Отчество
    academic_degree = db.Column(db.Text, nullable=True) # Учёная степень
    workplace = db.Column(db.Text, nullable=True) # Место работы
    position = db.Column(db.Text, nullable=True) # Кем работает человек
    research_field = db.Column(db.Text, nullable=True) # Научное направление
    phone = db.Column(db.Text, nullable=True) # Номер телефона
    created_at = db.Column(db.Date, server_default=db.func.now()) # Дата создания аккаунта
    
    # 1:N — один пользователь, много участий
    participations = db.relationship(
        "Participation", back_populates="user", cascade="all, delete-orphan"
    )

    # 1:N — один пользователь создал много конференций. Отношения с организатором, который создал много конференций.
    created_conferences = db.relationship("Conference", back_populates="creator")



# ---------- Таблица участников конференций ----------
class Participation(db.Model):
    __tablename__ = "participations"
    id = db.Column(db.Integer, primary_key=True) # id
    role = db.Column(db.Text, nullable=False) # роли organizer — организатор, speaker — докладчик, participant — участник.
    report_topic = db.Column(db.Text, nullable=True)  # Тема доклада у докладчика
    registered_at = db.Column(db.Date, server_default=db.func.now())


    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable = False)
    conference_id = db.Column(db.Integer, db.ForeignKey("conferences.id"), nullable = False)

    # Пара "пользователь-конференция" должна быть уникальной
    __table_args__ = (
        db.UniqueConstraint("user_id", "conference_id", name="uq_user_conference"),
    )


    # Связь с пользователем
    user = db.relationship("User", back_populates="participations")

    # Связь с конференцией
    conference = db.relationship("Conference", back_populates="participations")


# ---------- Таблица конференций ----------
class Conference(db.Model):
    __tablename__ = "conferences"
    id = db.Column(db.Integer, primary_key=True) # id
    title = db.Column(db.Text, nullable=False) # title
    topic = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    fee = db.Column(db.Integer, nullable=False) # Оргвзнос
    format = db.Column(db.Text, nullable=False, server_default="offline") # offline — очно, online — онлайн, hybrid — смешанный
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.Date, server_default=db.func.now())
    creator = db.relationship("User", back_populates="created_conferences")

    participations = db.relationship(
        "Participation", back_populates="conference", cascade="all, delete-orphan"
    )                  

