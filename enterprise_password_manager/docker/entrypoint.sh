#!/bin/bash
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Creating cache tables..."
python manage.py createcachetable

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser if not exists..."
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
import os
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@epm.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123456')
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password, full_name='Admin')
    print(f'Superuser {email} created')
else:
    print(f'Superuser {email} already exists')
EOF

echo "Starting application..."
exec "$@"
