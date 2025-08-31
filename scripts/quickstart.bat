@echo off
REM Quick start script for the hospital backend on Windows.

echo Creating virtual environment...
python -m venv .venv
call .\.venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo Copying environment file...
IF NOT EXIST .env (
  copy .env.example .env
)

echo Applying migrations and loading seed data...
python manage.py migrate --noinput
python manage.py loaddata fixtures\seed_all.json

echo Starting development server on http://0.0.0.0:8000 ...
python manage.py runserver 0.0.0.0:8000