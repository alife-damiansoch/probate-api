#!/bin/sh

set -e

# replacing the placeholders in the default.conf.tpl file with the actual environment variables
# and save it as a new conf file. envsubst < /etc/nginx/default.conf.tpl > /etc/nginx/conf.d/default.conf
envsubst < /etc/nginx/default.conf.tpl > /etc/nginx/conf.d/default.conf

# tells nginx to run in the foreground, meaning not as a background process
nginx -g 'daemon off;'