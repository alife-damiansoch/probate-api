# This is a server block configuration for Nginx
#
#
# It is used to serve a Django application with uWSGI and Nginx
#
# listen ${LISTEN_PORT}: This tells Nginx to listen to a specific port,
#   the actual port number is provided by the ${LISTEN_PORT} environment variable
#
# location /static { alias /vol/static }: This is a location block for serving static files.
#   'alias /vol/static' tells Nginx that static files are located in the /vol/static directory on the server
#
# location /: This block is responsible for handling all other incoming HTTP requests
#
# uwsgi_pass ${APP_HOST}:${APP_PORT}:
#   Passes requests to the uWSGI application server that is running on the host and port provided
#   by ${APP_HOST} and ${APP_PORT} respectively
#
# include /etc/nginx/uwsgi_params:
#   Includes some necessary parameters that are needed for the communication between uWSGI and Nginx
#
# client_max_body_size 10M: The maximum allowable size for the client's HTTP request body.
#   If a client's request body size is larger than 10M,
#   the server responds with a 413 Request Entity Too Large status.


server {
    listen ${LISTEN_PORT};

    location /static {
        alias /vol/static;
    }

    location /static/media/uploads/ {
        deny all;
    }

    location / {
        uwsgi_pass              ${APP_HOST}:${APP_PORT};
        include                 /etc/nginx/uwsgi_params;
        client_max_body_size    10M;
    }
}