FROM node:24-slim AS css
WORKDIR /app
COPY package.json .
COPY package-lock.json .

RUN npm ci

COPY . .

RUN npm run css:build

FROM python:3.14-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends gettext && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .

RUN uv sync --frozen --no-dev

COPY . .
COPY --from=css /app/static/css/app.css static/css/app.css
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput
RUN SECRET_KEY=build-only python manage.py compilemessages --ignore=.venv

ENV MEDIA_ROOT=/data/media
ENV DATABASE_URL=sqlite:////data/db.sqlite3
ENV SECRET_KEY_FILE=/data/secret_key
RUN mkdir -p /data

RUN useradd --create-home app
RUN chown app /data

RUN chmod +x docker-entrypoint.sh

USER app

EXPOSE 8000
ENTRYPOINT [ "./docker-entrypoint.sh" ]
CMD [ "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "300", "--access-logfile", "-" ]