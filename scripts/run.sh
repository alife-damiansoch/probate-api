#!/bin/sh

# This line ensures that the script stops if any command fails
set -e

# Custom Django management command to wait for the database to be ready
python manage.py wait_for_db

# Django management command for collecting all static files into a single directory that can be served easily
# "--noinput" is used to automatically overwrite existing files without asking for confirmation
python manage.py collectstatic --noinput

# Django management command that applies database migrations
# It applies changes made to the models (like adding a field, deleting a model) into the database schema
python manage.py migrate

# Start the uwsgi server with the following configurations:
# "--socket :9000" makes the application listen on socket 9000
# "--workers 4" specifies that 4 worker processes should be started
# "--master" makes the uwsgi instance a master process that controls the worker processes
# "--enable-threads" enables multi-threading
# "--module app.wsgi" specifies the python WSGI module to be run
uwsgi --socket :9000 --workers 4 --master --enable-threads --module app.wsgi