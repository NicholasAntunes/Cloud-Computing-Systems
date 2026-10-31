# API image. Settings come from environment variables (docs/PLAN.md §9), never from a
# file in the image: .dockerignore keeps .env out.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, in their own layer, so a code change doesn't reinstall them.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Code, alembic.ini and migrations/ (see .dockerignore). Owned by root, so the app
# user below can read it but not change it.
COPY . .

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000

# Serve. --proxy-headers: take the client address from Caddy's X-Forwarded-For,
# trusted only from the IPs in FORWARDED_ALLOW_IPS (default 127.0.0.1).
# TODO(task 3): run `alembic upgrade head &&` first once migrations exist.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
