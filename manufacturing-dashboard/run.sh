#!/usr/bin/env bash
set -e

source venv/bin/activate
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
