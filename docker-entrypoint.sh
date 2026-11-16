#!/bin/sh
set -e

# Without an explicit SECRET_KEY, generate one on the first start and keep it in the
# data volume, so it survives image updates. settings.py reads it via SECRET_KEY_FILE.
# Done here and not in settings.py: every gunicorn worker loads the settings, on the
# very first start two workers would each write their own key.
if [ -z "$SECRET_KEY" ] && [ ! -s "$SECRET_KEY_FILE" ]; then
    echo "No SECRET_KEY set, generating one in $SECRET_KEY_FILE"
    python -c "import secrets; print(secrets.token_urlsafe(50))" > "$SECRET_KEY_FILE"
    chmod 600 "$SECRET_KEY_FILE"
fi

python manage.py migrate --noinput

exec "$@"
