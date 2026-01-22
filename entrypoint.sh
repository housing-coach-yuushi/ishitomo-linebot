#!/bin/sh
set -e

# Use PORT environment variable, default to 8080
PORT=${PORT:-8080}

# Run uvicorn
exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT
