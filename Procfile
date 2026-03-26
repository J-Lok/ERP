web: gunicorn --chdir management_system management_system.wsgi:application --workers 2 --threads 2 --bind 0.0.0.0:$PORT
release: python management_system/manage.py migrate --noinput && python management_system/manage.py collectstatic --noinput
