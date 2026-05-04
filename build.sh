#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python management_system/manage.py compilemessages
python management_system/manage.py collectstatic --noinput
python management_system/manage.py migrate --noinput
