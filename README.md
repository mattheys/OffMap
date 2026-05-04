# OffMap

OffMap runs a fully self-hosted OpenStreetMap web server from `planet.osm.pbf`.

- Map UI and vector tiles are served locally (no CDN at runtime).
- Global low-detail tiles are available up to `LOW_MAX_ZOOM` (default `z8`).
- A selected high-detail region from `HIGH_DETAIL_REGION` is available up to `HIGH_MAX_ZOOM` (default `z14`).
- Offline search is built for the selected high-detail region.
- Planet data can refresh on a schedule.

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
docker compose up --build
```

By default, `docker-compose.yml` uses `HIGH_DETAIL_REGION=California` and stores data in the named volume `offmap-data`.

### Option 2: docker run

```bash
docker build -t offmap .
docker run --rm -p 8080:8080 \
  -e HIGH_DETAIL_REGION="California" \
  -e AUTO_UPDATE=true \
  -e UPDATE_CRON="0 3 1 * *" \
  -e PLANET_MAX_AGE_DAYS=30 \
  -v offmap-data:/data \
  offmap
```

Open `http://localhost:8080`.

## First Startup Expectations

- First startup downloads planet data and builds tiles/search indexes; this can take a long time.
- Persistent data lives under `/data` (mount a Docker volume or host path).
- The API starts at port `8080`.

Check readiness:

```bash
curl http://localhost:8080/status
```

When ready, response includes values like:

- `region`
- `updated_at`
- `planet_file`
- `low_mbtiles`
- `high_mbtiles`
- `search_db`

## Choosing `HIGH_DETAIL_REGION`

You can set `HIGH_DETAIL_REGION` using:

- Region display name (for example `California`)
- Region id/slug (for example `us/california`)
- ISO code when available (for example `US-CA`)

The full supported list is in `REGIONS.md`, now organized as a tree for easier navigation.

Useful checks:

```bash
curl "http://localhost:8080/regions?limit=50"
```

## Configuration

- `HIGH_DETAIL_REGION` (required for practical use): region name, slug/id, or ISO from `REGIONS.md`
- `PLANET_URL` (default `https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf`)
- `LOW_MAX_ZOOM` (default `8`)
- `HIGH_MAX_ZOOM` (default `14`)
- `TILE_THREADS` (default `1`; increase only if CPU/RAM allow)
- `STARTUP_IMPORT` (default `true`; set `false` to skip build on app startup)
- `AUTO_UPDATE` (default `true`)
- `UPDATE_CRON` (default `0 3 1 * *`, monthly at 03:00 on day 1)
- `PLANET_MAX_AGE_DAYS` (default `30`; skip planet download when local file is newer)

## Data Layout

All persistent data is stored under `/data`:

- `/data/planet/planet.osm.pbf`
- `/data/tiles/low.mbtiles`
- `/data/tiles/high.mbtiles`
- `/data/search/search.db`
- `/data/state/status.json`

## Endpoints

- `GET /` map UI
- `GET /style.json` map style used by the UI
- `GET /tiles/{z}/{x}/{y}.pbf` vector tile endpoint
- `GET /search?q=...&limit=20` offline search
- `GET /status` pipeline/build status
- `GET /regions?limit=100` available regions

## Notes

- Runtime internet is required only for downloading/updating planet data.
- Overzoom fallback from low-detail tiles avoids blank maps outside the high-detail region.
- High-detail extraction uses Geofabrik region bounding boxes.
