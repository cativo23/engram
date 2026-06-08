# Engram API + static recall console.
# Single-stage: small slim base, install pinned deps, copy the package (which
# includes engram/web/ static assets), serve with uvicorn.
FROM python:3.14-slim

WORKDIR /app

# Install dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (the `engram` package bundles engram/web/ static files).
COPY engram ./engram

EXPOSE 8000

# Bind 0.0.0.0 so the port is reachable from outside the container.
CMD ["uvicorn", "engram.main:app", "--host", "0.0.0.0", "--port", "8000"]
