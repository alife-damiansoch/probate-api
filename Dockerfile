FROM python:3.9-alpine3.13
LABEL maintainer="damiansoch.ds@gmail.com"

ENV PYTHONUNBUFFERED 1

COPY ./requirements.txt /tmp/requirements.txt
COPY ./requirements.dev.txt /tmp/requirements.dev.txt
# uWSGI
COPY ./scripts /scripts
COPY app /app
WORKDIR /app
EXPOSE 8000

ARG DEV=false

# Install Python environment and dependencies
RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip && \
    apk add --update --no-cache postgresql-client && \
    apk add --update --no-cache --virtual .tmp-build-deps \
      build-base postgresql-dev musl-dev linux-headers && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    if [ "$DEV" = "true" ]; then /py/bin/pip install -r /tmp/requirements.dev.txt; fi

# Clean up temporary files
RUN rm -rf /tmp && \
apk del .tmp-build-deps

# Create the non-root user and adjust file permissions
RUN adduser --disabled-password --no-create-home django-user && \
    #    this is added for configuring the static files
    mkdir -p /vol/web/media && \
    mkdir -p /vol/web/static && \
    #  changing the owner of the directory
    chown -R django-user:django-user /vol && \
    #  changing the permissions to the directory
    chmod -R 755 /vol && \
    # make sure that scripts directory is executable
    chmod -R +x /scripts


ENV PATH="/scripts:/py/bin:$PATH"

# Switch to the non-root user
USER django-user

# running the application
# overwritten in the docker-compose for dev
CMD ["run.sh"]