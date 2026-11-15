# API

Приложение возвращает HTML и принимает HTML-формы (`application/x-www-form-urlencoded`). Единственный JSON-маршрут — `/health`. Swagger UI, ReDoc и OpenAPI-схема не подключены.

## Сводка эндпоинтов

| Метод | Путь | Авторизация | Описание |
|---|---|---|---|
| GET | `/` | — | Каталог, по две конференции на страницу |
| GET, POST | `/register/` | — | Форма и обработка регистрации |
| GET, POST | `/authentication/` | — | Форма и обработка входа |
| GET, POST | `/goout` | Сессия | POST завершает сессию; GET только перенаправляет |
| GET, POST | `/conferences/new` | Сессия | Создание конференции |
| GET | `/conferences/<int:id_conference>/` | Сессия | Подробности конференции |
| GET, POST | `/conferences/<int:id_conference>/join` | Сессия | Запись участником или докладчиком |
| GET | `/health` | — | Проверка приложения, БД и версии |
| GET | `/static/<path:filename>` | — | Статические CSS/JS Flask |

## Авторизация

После успешного POST на `/authentication/` Flask-Login сохраняет идентификатор пользователя в подписанной cookie-сессии Flask. Клиент должен сохранять и передавать cookie. Сессионные данные подписаны `SECRET_KEY`, но не зашифрованы. Пароль в сессию не записывается.

Гость на защищённом маршруте получает `302` на `/authentication/` и flash-сообщение. Параметр возврата `next` обработчиком не используется: успешный вход ведёт на главную. JWT и заголовок Bearer не используются.

## Пользователи

### GET /register/ и POST /register/

GET возвращает HTML-форму (`200`). Поля POST:

| Поля | Назначение |
|---|---|
| `login`, `password` | Логин и исходный пароль |
| `name`, `surname` | Имя и фамилия |
| `patronymic` | Отчество |
| `academic_degree`, `workplace`, `position` | Степень, место работы, должность |
| `research_field`, `phone` | Научное направление и телефон |

Первые четыре поля обязательны в HTML. Обработчик читает форму без отдельной серверной схемы валидации. `login` уникален в БД. Пароль хэшируется `generate_password_hash` Werkzeug; конкретный алгоритм определяется установленной версией библиотеки.

| Ситуация | Ответ |
|---|---|
| Успешная регистрация | `302` → `/authentication/`, flash об успехе |
| Логин занят | `200`, снова форма и flash |
| Исключение при сохранении | rollback, `200`, форма с текстом ошибки |

### GET /authentication/ и POST /authentication/

GET: HTML, `200`. POST: `login`, `password`. Пароль проверяется `check_password_hash`.

Успех: `302` → `/`. Неверные данные: `302` → `/authentication/` с flash-сообщением. Это не JSON-ошибка `401`.

### POST /goout

Требует входа. Вызывает `logout_user`, добавляет сообщение и отвечает `302` → `/`. GET по тому же пути не завершает сессию, только отвечает редиректом на главную.

## Конференции

### GET /

Query-параметр `page`: целое число, по умолчанию `1`. Сортировка `start_date DESC`, размер страницы `2`, `error_out=False`. На странице за пределами каталога список может быть пустым. Гость видит каталог; для вошедшего пользователя дополнительно выбираются его участия.

### GET /conferences/new и POST /conferences/new

Требуют входа. GET возвращает форму (`200`).

| Поле POST | Назначение |
|---|---|
| `title`, `topic` | Название и тематика |
| `description` | Необязательное описание |
| `location` | Место проведения |
| `start_date`, `end_date` | Даты в формате `YYYY-MM-DD` |
| `fee` | Целочисленный оргвзнос; HTML задаёт минимум 0 |
| `format` | `offline`, `online`, `hybrid`; отсутствующее или неизвестное значение заменяется на `offline` |

В БД обязательны все перечисленные поля, кроме `description`; `format` имеет default. Создатель определяется из сессии. Конференция и участие `organizer` сохраняются одной транзакцией.

Успех: `302` → `/conferences/ID/`. Название уже существует: `200` с формой и сообщением. Ошибка сохранения: rollback и `200` с текстом ошибки. Уникальность названия на уровне БД не закреплена.

### GET /conferences/ID/

Требует входа. Возвращает HTML с данными конференции и статусом участия (`200`). Счётчик записавшихся исключает организатора. Если конференции нет — `302` на `/`, а не `404`. Некорректный идентификатор, не подходящий под Flask-конвертер `int`, не совпадёт с маршрутом.

### GET /conferences/ID/join и POST /conferences/ID/join

Требуют входа. При существующей конференции и отсутствии участия GET возвращает форму (`200`).

POST: `role=participant` либо `role=speaker`; для докладчика — `report_topic`. Для любой роли, отличной от `speaker`, тема принудительно становится `None`.

| Ситуация | Ответ |
|---|---|
| Успешная запись | `302` → `/` |
| Конференции нет | `302` → `/`, flash |
| Уже записан, включая организатора | `302` → `/conferences/ID/`, flash |
| Ошибка записи | rollback, `200`, форма с flash |

HTML предлагает две роли и требует тему у докладчика через JavaScript. **Сервер не проверяет список ролей и непустоту темы**: прямой запрос может сохранить иное значение, в том числе `organizer`. Это ограничение реализации, см. [known-issues.md](known-issues.md).

## Проверка работоспособности

### GET /health

Выполняет `SELECT 1`. При успехе — `200`:

```json
{"status":"ok","database":"ok","version":"local"}
```

`version` берётся из `APP_VERSION`, по умолчанию `local`. Ошибка SQL даёт `500` с `status=error` и строкой исключения в `database`. Проверка не подтверждает наличие всех прикладных таблиц и совпадение версии миграций.

## Примеры на curl

Пример для локального стенда; использовать отдельные демонстрационные реквизиты. Cookie-файл после входа содержит активную сессию.

```bash
BASE=http://localhost:8000

curl -i -X POST "$BASE/register/" \
  --data-urlencode 'login=demo-organizer' \
  --data-urlencode 'password=REPLACE_ME' \
  --data-urlencode 'name=Иван' \
  --data-urlencode 'surname=Иванов'

curl -i -c organizer.cookies "$BASE/authentication/" \
  --data-urlencode 'login=demo-organizer' \
  --data-urlencode 'password=REPLACE_ME'

curl -i -b organizer.cookies "$BASE/conferences/new" \
  --data-urlencode 'title=Научная конференция' \
  --data-urlencode 'topic=Автоматизация' \
  --data-urlencode 'location=Москва' \
  --data-urlencode 'start_date=2027-03-10' \
  --data-urlencode 'end_date=2027-03-12' \
  --data-urlencode 'fee=1000' \
  --data-urlencode 'format=hybrid'

curl -b organizer.cookies "$BASE/conferences/1/"
curl "$BASE/?page=2"
curl --fail "$BASE/health"
curl -i -b organizer.cookies -X POST "$BASE/goout"
```

ID `1` заменить на фактический из `Location` ответа создания. Для записи зарегистрировать и авторизовать второго пользователя с отдельным cookie-файлом:

```bash
curl -i -b guest.cookies "$BASE/conferences/1/join" \
  --data-urlencode 'role=speaker' \
  --data-urlencode 'report_topic=Миграции в CI/CD'
```

Для проверки редиректов примеры используют `-i` без `-L`: автоматический переход скроет исходный `302`.
