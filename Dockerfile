# ---- builder ----
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential default-libmysqlclient-dev pkg-config \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---- runtime ----
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 运行时其实只需要运行库，不需要 *-dev，体积更小（可选）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

COPY . .

# 用环境变量指定端口/并发，默认仍兼容本地 8000
CMD ["sh", "-c", "gunicorn ${ASGI_APP:-hospital.asgi:application} \
  -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} \
  --workers=${WEB_CONCURRENCY:-2} --threads=${THREADS:-8} --timeout=${TIMEOUT:-120}"]
