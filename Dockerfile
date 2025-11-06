FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron gdal-bin libgdal-dev netcat-traditional postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo "*/1 * * * * cd /app && . /etc/environment && flock -n /tmp/earthquake.lock /usr/local/bin/python /app/scripts/earthquake_pipeline.py >> /var/log/cron.log 2>&1" \
    > /etc/cron.d/earthquake-cron && \
    chmod 0644 /etc/cron.d/earthquake-cron && \
    crontab /etc/cron.d/earthquake-cron

EXPOSE 8000

ENTRYPOINT ["python", "/app/scripts/docker_entrypoint.py"]