FROM python:3.12-slim

# configure pip and python
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# create user and group for the application
RUN groupadd --system --gid 1001 app \
 && useradd --system --create-home --home-dir /app --uid 1001 --gid 1001 app

# upgrade system, install required packages
# remove unused packages, clean apt cache
RUN apt update \
 && apt upgrade -y \
 && apt install -y libpq-dev gcc \
 && apt autoremove -y \
 && apt clean -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=1001:1001 requirements.txt .

RUN pip install -r requirements.txt

COPY --chown=1001:1001 . .

USER app

EXPOSE 8000

CMD ["scripts/start.sh"]
