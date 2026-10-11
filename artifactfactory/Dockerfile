# Artifact Factory — stdlib-only Python daemon (no third-party dependencies).
#
# Build context is this directory (the `artifactfactory` package itself). The
# package is copied to /app/artifactfactory so `python3 -m artifactfactory.daemon`
# resolves from /app.
FROM python:3.12-slim

WORKDIR /app

COPY . /app/artifactfactory/
COPY docker-entrypoint.py /app/docker-entrypoint.py

# Bind to all interfaces so the port is reachable from outside the container.
# Defaults for data/artifacts resolve to /app/_artifactfactory-data and
# /app/_artifacts (see config.py), which the compose file mounts as volumes.
ENV AF_HOST=0.0.0.0 \
    AF_PORT=8080 \
    AF_STORAGE=local \
    PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status == 200 else 1)"

CMD ["python3", "-m", "artifactfactory.daemon"]
