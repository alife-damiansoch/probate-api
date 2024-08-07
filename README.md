# probate_api

api for the probate app

### Docker commands:

    -   "django-admin startproject app ." - starting the app for the first time

  
    -   "python manage.py test"
    -   "python manage.py wait_for_db" - to check wait_for_db method
    -   "python manage.py makemigrations"
    -   "python manage.py wait_for_db && python manage.py migrate"
    -   "python manage.py createsuperuser"

    -   "python manage.py startapp user" - this is for starting creating new app (for api queries)

### Git commands:

    -   git add .
    -   git commit -am "Commit message"
    -   git push origin

## Errors

#### - Migrations:

#### - Be careful with this, and do not do this on live databases this removes all the data...

        -   .InconsistentMigrationHistory: Migration admin.0001_initial is applied before its dependency core.0001_initial on database 'default'
            
            -   This is because the migrations for a default django users were applied 
                and we need to clear the data in the database

                -   docker volume ls - to list the volumes
                -   docker volume rm probate-project-try_dev-db-data - the name of the volume

## - after deployment settings are completed you can run this to check if everything works

#### - you change the port in you docker-compose-deploy to 80:8000 (remember to change it back after the test)

        -   docker-compose -f docker-compose-deploy.yml up - you change the port in 