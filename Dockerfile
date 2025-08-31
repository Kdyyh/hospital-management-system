# ---- builder ----
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential default-libmysqlclient-dev pkg-config     && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---- runtime ----
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends     default-libmysqlclient-dev     && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*
COPY . .
CMD ["gunicorn", "hospital.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
