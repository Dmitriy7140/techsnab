FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=appsrc requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=appsrc manage.py .
COPY --from=appsrc config/ config/
COPY --from=appsrc landing/ landing/
COPY settings.py config/deployment.py
RUN python manage.py collectstatic --noinput \
    && groupadd --gid 10001 techsnab \
    && useradd --uid 10001 --gid 10001 --no-create-home techsnab \
    && install -d -o techsnab -g techsnab /var/lib/techsnab /var/lib/techsnab-reviews

ENV DJANGO_SETTINGS_MODULE=config.deployment
USER techsnab
EXPOSE 8000
CMD ["sh", "-ec", "python manage.py migrate --noinput; if [ \"${MIGRATE_REVIEWS:-0}\" = 1 ]; then python manage.py migrate reviews --database reviews --noinput; fi; exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2"]
