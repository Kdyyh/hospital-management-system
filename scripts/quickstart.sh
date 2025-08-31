#!/bin/bash
# Quick start script for the hospital backend.
#
# This script sets up a virtual environment, installs dependencies,
# runs migrations, loads the seed data and starts the development
# server.  Intended for Unix-like environments.

set -e

VENV=.venv

echo "Creating virtual environment..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Copying environment file..."
if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "Applying migrations and loading seed data..."
python manage.py migrate --noinput
python manage.py loaddata fixtures/seed_all.json

echo "Starting development server on http://0.0.0.0:8000 ..."
python manage.py runserver 0.0.0.0:8000