FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    osmium-tool \
    sqlite3 \
    tilemaker \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /usr/local/bin/supercronic \
    https://github.com/aptible/supercronic/releases/download/v0.2.39/supercronic-linux-amd64 \
    && chmod +x /usr/local/bin/supercronic

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/static/assets \
    && curl -fsSL -o /app/static/assets/maplibre-gl.js \
      https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js \
    && curl -fsSL -o /app/static/assets/maplibre-gl.css \
      https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css \
    && chmod +x /app/scripts/entrypoint.sh

VOLUME ["/data"]

ENV DATA_DIR=/data
ENV HIGH_DETAIL_REGION=Germany
ENV LOW_MAX_ZOOM=8
ENV HIGH_MAX_ZOOM=14
ENV TILE_THREADS=1
ENV STARTUP_IMPORT=true
ENV AUTO_UPDATE=true
ENV UPDATE_CRON="0 3 1 * *"
ENV PLANET_MAX_AGE_DAYS=30
ENV PLANET_URL=https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf

EXPOSE 8080

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
