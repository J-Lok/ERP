web: gunicorn management_system.wsgi:application --workers 2 --threads 2 --bind 0.0.0.0:$PORT
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
