#!/usr/bin/env bash

if [[ -z "${FLAG_2:-}" ]]; then
  echo "WARNING: FLAG_2 is not set"
fi

# --- Replace placeholder in /app/flag ---
if [[ -f "/app/flag" ]]; then
  if grep -q "REPLACE_THIS_STRING_WITH_SERVER_FLAG" "/app/flag"; then
    echo "Replacing placeholder in flag with $FLAG_2"
    sed -i "s/REPLACE_THIS_STRING_WITH_SERVER_FLAG/${FLAG_2}/g" /app/flag
  fi
else
  echo "WARNING: /app/flag not found, skipping"
fi

# --- Start the server ---
echo "Starting server..."
exec gunicorn -b 0.0.0.0:5000 --access-logfile - --error-logfile - server:app

