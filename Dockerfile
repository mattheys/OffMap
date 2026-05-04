FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    osmium-tool \
    sqlite3 \
    tilemaker \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /usr/local/bin/supercronic \
    https://github.com/aptible/supercronic/releases/download/v0.2.39/supercronic-linux-amd64 \
    && chmod +x /usr/local/bin/supercronic

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/static/assets /app/tilemaker /app/coastline \
    /app/landcover/ne_10m_urban_areas \
    /app/landcover/ne_10m_antarctic_ice_shelves_polys \
    /app/landcover/ne_10m_glaciated_areas \
    && curl -fsSL -o /app/static/assets/maplibre-gl.js \
      https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js \
    && curl -fsSL -o /app/static/assets/maplibre-gl.css \
      https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css \
    && curl -fsSL -o /app/tilemaker/config-openmaptiles.json \
      https://raw.githubusercontent.com/systemed/tilemaker/master/resources/config-openmaptiles.json \
    && curl -fsSL -o /app/tilemaker/process-openmaptiles.lua \
      https://raw.githubusercontent.com/systemed/tilemaker/master/resources/process-openmaptiles.lua \
    && curl -fsSL -o /tmp/water-polygons.zip \
      https://osmdata.openstreetmap.de/download/water-polygons-split-4326.zip \
    && unzip -q -j /tmp/water-polygons.zip -d /app/coastline \
    && curl -fsSL -o /tmp/ne_10m_urban_areas.zip \
      https://naciscdn.org/naturalearth/10m/cultural/ne_10m_urban_areas.zip \
    && unzip -q -j /tmp/ne_10m_urban_areas.zip -d /app/landcover/ne_10m_urban_areas \
    && curl -fsSL -o /tmp/ne_10m_antarctic_ice_shelves_polys.zip \
      https://naciscdn.org/naturalearth/10m/physical/ne_10m_antarctic_ice_shelves_polys.zip \
    && unzip -q -j /tmp/ne_10m_antarctic_ice_shelves_polys.zip -d /app/landcover/ne_10m_antarctic_ice_shelves_polys \
    && curl -fsSL -o /tmp/ne_10m_glaciated_areas.zip \
      https://naciscdn.org/naturalearth/10m/physical/ne_10m_glaciated_areas.zip \
    && unzip -q -j /tmp/ne_10m_glaciated_areas.zip -d /app/landcover/ne_10m_glaciated_areas \
    && rm -f /tmp/water-polygons.zip /tmp/ne_10m_urban_areas.zip /tmp/ne_10m_antarctic_ice_shelves_polys.zip /tmp/ne_10m_glaciated_areas.zip \
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
ENV TILEMAKER_CONFIG_PATH=/app/tilemaker/config-openmaptiles.json
ENV TILEMAKER_PROCESS_PATH=/app/tilemaker/process-openmaptiles.lua
ENV PLANET_URL=https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf

EXPOSE 8080

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
