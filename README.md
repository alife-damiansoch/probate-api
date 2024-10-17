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

Linux server step by step commands -

DJANGO:

sudo apt update

sudo apt upgrade

sudo apt install python3-pip python3-dev libpq-dev postgresql postgresql-contrib nginx curl python3-venv git
git-credential-manager-core

1. Switch to the PostgreSQL user:

    1. sudo -i -u postgres

    2. Psql

    3. CREATE DATABASE your\_database\_name; CREATE USER your\_username WITH PASSWORD 'your\_password';

    4. ALTER ROLE your\_username SET client\_encoding TO 'utf8'

ALTER ROLE your\_username SET default\_transaction\_isolation TO 'read committed'ALTER ROLE your\_username SET timezone
TO 'Europe/Dublin'GRANT ALL PRIVILEGES ON DATABASE your\_database\_name TO your\_username

1. \\q

2. Exit

3. GIT

    1. sudo apt install git

    2. git --version

    3. cd ~

    4. git
       clone [https://github.com/your-username/your-repository.git](https://github.com/your-username/your-repository.git)

    5. If needed ssh key adding:

        1. **Generate a new SSH key pair**: ssh-keygen -t rsa -b 4096
           -C "[your\_email@example.com](mailto:your_email@example.com)"

        2. **Start the SSH agent**:eval "$(ssh-agent -s)"

        3. **Add your SSH private key to the SSH agent**:ssh-add ~/.ssh/id\_rsa

        4. **Copy the SSH public key to your clipboard**:cat ~/.ssh/id\_rsa.pub

**Add the SSH key to your Git service**:

* **For GitHub**:

    * Go to your GitHub account settings.

    * Navigate to "SSH and GPG keys".

    * Click "New SSH key".

    * Paste your SSH key into the "Key" field and give it a title.

    * Click "Add SSH key".


1. Test Your SSH Connection:ssh -T git@github.com

2. cd your-repository

3. Set Up Your Django Project

    1. python3 -m venv venv

    2. source venv/bin/activate

    3. pip install -r requirements.txt

    4. **Switch to the postgres user**:sudo -i -u postgres

    5. python manage.py migrate

    6. python manage.py runserver

### The command to go throught all solicitors and users and add their emails into the AssociatedEmials

To execute the management command, run the following from your command line:

python manage.py add_emails

This will process all users and solicitors, adding their emails to the AssociatedEmail model as needed.
