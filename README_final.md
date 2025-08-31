# Hospital Backend Service

This repository contains a fully‑functional Django + DRF backend that
implements the API contract defined by the front‑end mock files
(`endpoints.js` and `sim-mock.js`).  The project models groups
(departments), administrators, patients, queues, inquiries and
messaging.  All routes match exactly the paths expected by the
front‑end and return JSON responses with the same field names and
semantics.

## Features

* **Token based authentication** via `/api/auth/login` with support for
  roles (`patient`, `admin`, `core`, `super`) and optional
  group binding information.
* **Administrative dashboard** summarising waiting, in‑hospital and
  lost patients along with alerts.
* **Patient management** including listing and exporting patients with
  group‑level filtering.  Only `admin`, `core` and `super` users may
  access this list.
* **Department/group management** for publishing/unpublishing
  departments, retrieving details, managing members and adjusting
  quotas.
* **Queue management** including per‑patient queue status, queue
  item prioritisation, administrative queue control (marking items
  completed automatically progresses the next waiting item to
  “就诊中”), statistics and broadcast messages.
* **Inquiry centre** for administrators and online patient enquiries
  for patients with replies and status updates.
* **Message endpoints** returning static system messages for admins and
  patients.
* **Comprehensive test suite** covering role isolation, queue
  transitions and patient permissions using `pytest`/`pytest-django`.
* **Pre‑loaded seed data** matching the front‑end mock via
  `fixtures/seed_all.json`.
* **Dockerised deployment** using a single service with automatic
  migrations and seed loading.
* **OpenAPI/Swagger documentation** available at `/swagger/` once the
  server is running.

## Project Structure

```
hospital-backend/
├─ manage.py                  # Django entry point
├─ requirements.txt           # Python dependencies
├─ README.md                  # Project overview and instructions
├─ .env.example               # Template environment configuration
├─ .env                       # Default environment for local use
├─ docker-compose.yml         # Docker Compose definition
├─ Dockerfile                 # Docker build specification
├─ scripts/
│  ├─ quickstart.sh           # Bash helper for local quickstart
│  └─ quickstart.bat          # Windows helper for local quickstart
├─ hospital/
│  ├─ settings.py             # Django settings
│  ├─ urls.py                 # URL dispatcher including API routes and Swagger
│  └─ ...
├─ core/
│  ├─ models.py               # Database models
│  ├─ auth.py                 # Token authentication & login view
│  ├─ permissions.py          # Custom permission classes
│  ├─ routers.py              # API endpoints registered to views
│  ├─ views/                  # API view functions grouped by feature
│  ├─ tests/                  # Pytest test cases
│  └─ ...
└─ fixtures/
   └─ seed_all.json           # Seed data loaded automatically on start
```

## Quickstart (Local)

1. **Create a virtual environment and install dependencies**

   ```bash
   cd hospital-backend
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows use .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Prepare the environment**

   Copy the example environment and adjust values as needed:

   ```bash
   cp .env.example .env
   ```

3. **Run migrations and load seed data**

   ```bash
   python manage.py migrate
   python manage.py loaddata fixtures/seed_all.json
   ```

4. **Start the development server**

   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

The API will be available at `http://localhost:8000`.  OpenAPI/Swagger
documentation can be accessed at `http://localhost:8000/swagger/`.

### Helper Scripts

Alternatively you can run the provided helper script which performs
all of the above steps:

```bash
./scripts/quickstart.sh

For a **universal one‑click startup**, use the top‑level `start.sh`
(or `start.bat` on Windows).  This wrapper will use Docker if it is
available on your system and fall back to the local quickstart if
Docker is not installed:

```bash
./start.sh
```

On Windows:

```cmd
start.bat
```
```

On Windows, run `scripts\quickstart.bat` instead.

## Quickstart (Docker)

You can run the backend in a container using Docker Compose.  This
method requires only Docker and Docker Compose to be installed:

```bash
cd hospital-backend
docker compose up --build -d
```

This will build the image, run database migrations, load the seed
data and start the Django development server on port 8000.  The
container reads environment variables from the `.env` file by
default.

## Default Accounts

The following accounts are created by the seed data and can be used
immediately after starting the application:

| Username | Password   | Role   | Group | Notes                           |
|---------|------------|--------|-------|--------------------------------|
| super   | super123   | super | ‑     | Global super administrator      |
| core    | core123    | core  | g1    | Core admin with leader role      |
| admin   | admin123   | admin | g1    | Administrator of group g1         |
| admin2  | admin2123  | admin | g2    | Administrator of group g2         |
| admin3  | admin3123  | admin | g3    | Administrator of group g3         |
| patient | patient123 | patient | g1  | Sample patient bound to g1       |
| patient2| patient2123| patient | g2  | Sample patient bound to g2       |
| patient3| patient3123| patient | g3  | Sample patient bound to g3       |

Administrators must authenticate via `POST /api/auth/login` to
receive a token.  Provide `username` and `password` (the role is
inferred).  Include the returned token in the `Authorization:
Token <token>` header for subsequent requests.

## Running Tests

Tests are written using `pytest` and live in `core/tests/`.  To run
them locally:

```bash
pytest -q hospital-backend/core/tests
```

These tests verify that:

* Only users with sufficient privileges can access protected
  resources.
* Group isolation is enforced when listing patients.
* Patients may only cancel their own queue items.
* Completing a queue item automatically progresses the next waiting
  item to “就诊中” and updates queue counters.

## Generating OpenAPI/Swagger Specification

The application includes [drf‑yasg](https://drf-yasg.readthedocs.io/)
for API documentation.  You can export the schema to a file by
running:

```bash
python manage.py generateschema --format openapi > openapi.yaml
```

Alternatively, browse `/swagger/` in your browser to view the
interactive Swagger UI.

## Notes

* The backend intentionally omits trailing slashes on API paths to
  mirror the front‑end configuration.
* Many endpoints contain simplified or stubbed logic (e.g. audit
  logs, messaging) matching the original mock.  Extend these views as
  needed for a production deployment.