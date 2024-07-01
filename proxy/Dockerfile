# Use the unprivileged Nginx image from Docker Hub as the base image. The "1-alpine" version is a lightweight version of Nginx.
FROM nginxinc/nginx-unprivileged:1-alpine

# Label the maintained email
LABEL maintainer = "damiansoch.ds@gmail.com"

# Copy the default.conf.tpl file from your project into the Docker image at path /etc/nginx/default.conf.tpl
COPY ./default.conf.tpl /etc/nginx/default.conf.tpl

# Copy the uwsgi_params file from your project into the Docker image at path /etc/nginx/uwsgi_params
COPY ./uwsgi_params /etc/nginx/uwsgi_params

# Copy the run.sh file from your project into the Docker image at path /run.sh
COPY ./run.sh /run.sh

# Set environment variables that the Nginx server will use
ENV LISTEN_PORT=8000
ENV APP_HOST=app
ENV APP_PORT=9000

# Switch to root user to perform commands that need root user permissions
USER root

# Create a directory for static content, set appropriate permissions,
# create the default configuration file for Nginx,
# change the ownership of the configuration file to 'nginx' user and make the run.sh file executable
RUN mkdir -p /vol/static && \
    chmod 755 /vol/static && \
    touch /etc/nginx/conf.d/default.conf && \
    chown nginx:nginx /etc/nginx/conf.d/default.conf && \
    chmod +x /run.sh

# Create a mount point named /vol/static. We can use this to share data between containers or between a container and the host.
VOLUME /vol/static

# Switch back to the 'nginx' user. It's good practice to not leave the container running as root for security reasons.
USER nginx

# Execute run.sh when the Docker container starts
CMD ["/run.sh"]