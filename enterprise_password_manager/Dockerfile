FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.0 \
    DJANGO_SETTINGS_MODULE=config.settings \
    ENVIRONMENT=production

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/staticfiles /app/media && \
    chmod -R 755 /app/logs /app/staticfiles /app/media

RUN python manage.py collectstatic --noinput

EXPOSE 8001

CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi:application"]
