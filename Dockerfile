# Backend image: the FastAPI app, the Starlink collector, and SQLite.
# The frontend is built/served separately (see frontend/Dockerfile) so the
# two can be updated, rebuilt, and scaled independently.

FROM python:3.12-slim

WORKDIR /app

# Copied and installed before the rest of the source so dependency
# installs are cached as long as pyproject.toml doesn't change.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# Everything StarPulse writes (config.toml, the SQLite database, logs)
# lives under one directory, so a single mounted volume there is enough
# to persist all of it across container restarts/recreations.
ENV STARPULSE_DATA_DIR=/data \
    STARPULSE_HOST=0.0.0.0 \
    STARPULSE_PORT=8000 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8000

# No curl/wget in the slim base image; urllib is stdlib, so this avoids
# adding a package just for the healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

CMD ["python", "-m", "starpulse"]
