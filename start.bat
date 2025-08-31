@echo off
REM Universal one‑click start script for Windows.
REM Attempts to use Docker Compose if available, otherwise falls back
REM to the local quickstart script.

WHERE docker >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
  REM Check if docker compose command is available
  docker compose version >nul 2>nul
  IF %ERRORLEVEL% EQU 0 (
    echo Docker detected. Building and starting the service with docker compose...
    IF NOT EXIST .env (
      copy .env.example .env
    )
    docker compose up --build -d
    echo Service is running on http://localhost:8000
    goto :eof
  )
)

echo Docker not available. Falling back to local environment setup...
call scripts\quickstart.bat