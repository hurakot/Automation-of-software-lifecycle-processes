FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .
ARG APP_VERSION=local
ENV APP_VERSION=$APP_VERSION
EXPOSE 5000

CMD ["sh", "-c", "flask db upgrade && gunicorn -b 0.0.0.0:5000 -w 2 app:app"]

