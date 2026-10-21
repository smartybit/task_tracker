#!/bin/sh
set -eu
python manage.py check
python manage.py migrate --noinput
python manage.py makemigrations --check --dry-run
python manage.py test --noinput -v 2
python manage.py seed_test_data
