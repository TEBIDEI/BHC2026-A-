web: gunicorn "app:create_app()" --workers 2 --threads 4 --timeout 60 --access-logfile -
release: flask --app app db upgrade
