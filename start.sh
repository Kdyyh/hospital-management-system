#!/bin/bash
# Universal one‑click start script.
#
# This script attempts to bring up the service either via Docker
# (preferred if Docker is installed) or falls back to a local
# quickstart using a virtual environment.  It is intended as a
# convenience wrapper around the existing helper scripts.

set -e

# Determine if docker compose is available
if command -v docker >/dev/null 2>&1 && command -v docker compose >/dev/null 2>&1; then
  echo "Docker detected. Building and starting the service with docker compose..."
  # Ensure .env exists so that docker compose picks up configuration
  if [ ! -f .env ]; then
    cp .env.example .env
  fi
  docker compose up --build -d
  echo "Service is running on http://localhost:8000"
else
  echo "Docker not available. Falling back to local environment setup..."
  ./scripts/quickstart.sh
fi