FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DOCLINT_STORAGE=/tmp/doclint-sessions
# Optional public CA bundle for builds behind an enterprise TLS proxy. Keep TLS
# and repository-signature verification enabled; the bundle is not kept in layers.
RUN --mount=type=secret,id=build_ca,mode=0444 \
    set -eu; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    apt_get() { if [ -f /run/secrets/build_ca ]; then apt-get -o Acquire::https::CaInfo=/run/secrets/build_ca "$@"; else apt-get "$@"; fi; }; \
    apt_get update; \
    apt_get install -y --no-install-recommends libreoffice-writer fonts-liberation fonts-crosextra-carlito fontconfig; \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY DocLint/requirements.txt ./requirements.txt
RUN --mount=type=secret,id=build_ca,mode=0444 \
    if [ -f /run/secrets/build_ca ]; then pip install --cert /run/secrets/build_ca --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY --chown=10001:10001 DocLint/ ./
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin doclint
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
