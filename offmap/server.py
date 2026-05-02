from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from offmap.config import SETTINGS, ensure_dirs
from offmap.pipeline import maybe_build_on_startup
from offmap.regions import load_regions

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"

app = FastAPI(title="OffMap")
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


def _tms_y(z: int, y: int) -> int:
    return (1 << z) - 1 - y


def _fetch_tile(db_path: Path, z: int, x: int, y: int) -> bytes | None:
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
            (z, x, _tms_y(z, y)),
        ).fetchone()
    if row is None:
        return None
    return row["tile_data"]


def _fetch_with_overzoom(z: int, x: int, y: int) -> bytes | None:
    if z <= SETTINGS.low_max_zoom:
        return _fetch_tile(SETTINGS.low_tiles_path, z, x, y)

    tile = _fetch_tile(SETTINGS.high_tiles_path, z, x, y)
    if tile is not None:
        return tile

    z0 = SETTINGS.low_max_zoom
    shift = z - z0
    parent_x = x >> shift
    parent_y = y >> shift
    return _fetch_tile(SETTINGS.low_tiles_path, z0, parent_x, parent_y)


@app.on_event("startup")
def _startup() -> None:
    ensure_dirs()
    maybe_build_on_startup()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/style.json")
def style() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.json")


@app.get("/tiles/{z}/{x}/{y}.pbf")
def tiles(z: int, x: int, y: int) -> Response:
    tile = _fetch_with_overzoom(z, x, y)
    if tile is None:
        raise HTTPException(status_code=404, detail="Tile not found")
    headers = {"Cache-Control": "public, max-age=3600"}
    if len(tile) >= 2 and tile[0] == 0x1F and tile[1] == 0x8B:
        headers["Content-Encoding"] = "gzip"
    return Response(
        content=tile,
        media_type="application/x-protobuf",
        headers=headers,
    )


@app.get("/search")
def search(q: str = Query(min_length=2), limit: int = Query(default=20, ge=1, le=100)) -> dict:
    if not SETTINGS.search_db_path.exists():
        raise HTTPException(status_code=503, detail="Search index is not ready")

    terms = [t for t in re.split(r"\s+", q.strip()) if t]
    cleaned_terms = [term.replace('"', "") for term in terms]
    fts_query = " ".join(f'"{term}"*' for term in cleaned_terms)
    if not fts_query:
        return {"query": q, "count": 0, "results": []}

    with sqlite3.connect(SETTINGS.search_db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT p.name, p.kind, p.lat, p.lon
            FROM places_fts f
            JOIN places p ON p.id = f.rowid
            WHERE places_fts MATCH ?
            ORDER BY bm25(places_fts)
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

    return {
        "query": q,
        "count": len(rows),
        "results": [
            {
                "name": row["name"],
                "kind": row["kind"],
                "lat": row["lat"],
                "lon": row["lon"],
            }
            for row in rows
        ],
    }


@app.get("/status")
def status() -> dict:
    if not SETTINGS.status_path.exists():
        return {"ready": False}
    return json.loads(SETTINGS.status_path.read_text())


@app.get("/regions")
def regions(limit: int = Query(default=100, ge=1, le=2000)) -> dict:
    items = load_regions()
    return {
        "total": len(items),
        "results": [
            {
                "name": item["name"],
                "id": item["id"],
                "iso": item.get("iso3166_2") or item.get("iso3166_1_alpha2"),
            }
            for item in items[:limit]
        ],
    }
