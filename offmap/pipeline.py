from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from offmap.config import SETTINGS, ensure_dirs
from offmap.regions import resolve_region


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _resolve_tilemaker_paths() -> tuple[str, str]:
    config_candidates = [
        SETTINGS.tilemaker_config_path,
        "/usr/share/tilemaker/config-openmaptiles.json",
        "/usr/share/tilemaker-openmaptiles/config-openmaptiles.json",
        "/usr/share/tilemaker/config.json",
    ]
    process_candidates = [
        SETTINGS.tilemaker_process_path,
        "/usr/share/tilemaker/process-openmaptiles.lua",
        "/usr/share/tilemaker-openmaptiles/process-openmaptiles.lua",
        "/usr/share/tilemaker/process.lua",
    ]

    config_path = next((p for p in config_candidates if p and Path(p).exists()), None)
    process_path = next((p for p in process_candidates if p and Path(p).exists()), None)

    if not config_path:
        raise FileNotFoundError(
            f"tilemaker config not found; checked: {', '.join(p for p in config_candidates if p)}"
        )
    if not process_path:
        raise FileNotFoundError(
            f"tilemaker process file not found; checked: {', '.join(p for p in process_candidates if p)}"
        )

    return config_path, process_path


def _download_planet() -> None:
    if SETTINGS.planet_path.exists():
        updated_at = datetime.fromtimestamp(SETTINGS.planet_path.stat().st_mtime, tz=timezone.utc)
        age = datetime.now(timezone.utc) - updated_at
        if age < SETTINGS.planet_max_age:
            return
    tmp = SETTINGS.planet_path.with_suffix(".tmp")
    _run(["curl", "-L", SETTINGS.planet_url, "-o", str(tmp)])
    tmp.replace(SETTINGS.planet_path)


def _trim_zoom(mbtiles_path: Path, max_zoom: int) -> None:
    with sqlite3.connect(mbtiles_path) as db:
        db.execute("DELETE FROM tiles WHERE zoom_level > ?", (max_zoom,))
        db.execute(
            "INSERT OR REPLACE INTO metadata(name, value) VALUES('maxzoom', ?)",
            (str(max_zoom),),
        )
        db.commit()
        db.execute("VACUUM")


def _build_low_tiles() -> None:
    config_path, process_path = _resolve_tilemaker_paths()
    if SETTINGS.low_tiles_path.exists():
        SETTINGS.low_tiles_path.unlink()
    _run(
        [
            "tilemaker",
            "--input",
            str(SETTINGS.planet_path),
            "--output",
            str(SETTINGS.low_tiles_path),
            "--config",
            config_path,
            "--process",
            process_path,
            "--threads",
            str(SETTINGS.tile_threads),
        ]
    )
    _trim_zoom(SETTINGS.low_tiles_path, SETTINGS.low_max_zoom)


def _build_high_extract() -> dict:
    region = resolve_region(SETTINGS.region)
    bbox = region["bbox"]
    if SETTINGS.region_extract_path.exists():
        SETTINGS.region_extract_path.unlink()
    _run(
        [
            "osmium",
            "extract",
            "--bbox",
            f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            str(SETTINGS.planet_path),
            "-o",
            str(SETTINGS.region_extract_path),
            "--overwrite",
        ]
    )
    return region


def _build_high_tiles() -> None:
    config_path, process_path = _resolve_tilemaker_paths()
    if SETTINGS.high_tiles_path.exists():
        SETTINGS.high_tiles_path.unlink()
    _run(
        [
            "tilemaker",
            "--input",
            str(SETTINGS.region_extract_path),
            "--output",
            str(SETTINGS.high_tiles_path),
            "--config",
            config_path,
            "--process",
            process_path,
            "--threads",
            str(SETTINGS.tile_threads),
        ]
    )
    _trim_zoom(SETTINGS.high_tiles_path, SETTINGS.high_max_zoom)


def _feature_name(props: dict) -> str | None:
    if props.get("name"):
        return props["name"]
    for key in ("addr:housename", "addr:street", "brand"):
        if props.get(key):
            return props[key]
    return None


def _build_search_index() -> None:
    if SETTINGS.search_db_path.exists():
        SETTINGS.search_db_path.unlink()

    with sqlite3.connect(SETTINGS.search_db_path) as db:
        db.execute("CREATE TABLE places(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, lat REAL, lon REAL)")
        db.execute("CREATE VIRTUAL TABLE places_fts USING fts5(name, kind, content='places', content_rowid='id')")

        proc = subprocess.Popen(
            [
                "osmium",
                "export",
                str(SETTINGS.region_extract_path),
                "-f",
                "geojsonseq",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None

        inserted = 0
        for line in proc.stdout:
            if not line.strip():
                continue
            try:
                feature = json.loads(line)
            except json.JSONDecodeError:
                continue
            props = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates")
            if not coords:
                continue
            name = _feature_name(props)
            if not name:
                continue

            kind = (
                props.get("amenity")
                or props.get("shop")
                or props.get("tourism")
                or props.get("place")
                or props.get("highway")
                or props.get("building")
                or "feature"
            )

            lon, lat = _best_point(geometry)
            if lat is None or lon is None:
                continue
            cur = db.execute(
                "INSERT INTO places(name, kind, lat, lon) VALUES(?, ?, ?, ?)",
                (name, kind, lat, lon),
            )
            db.execute(
                "INSERT INTO places_fts(rowid, name, kind) VALUES(?, ?, ?)",
                (cur.lastrowid, name, kind),
            )
            inserted += 1
            if inserted % 5000 == 0:
                db.commit()

        if proc.wait() != 0:
            raise RuntimeError("osmium export failed while building search index")
        db.commit()


def _best_point(geometry: dict) -> tuple[float | None, float | None]:
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geom_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        return float(coordinates[0]), float(coordinates[1])
    if geom_type == "LineString" and coordinates:
        p = coordinates[len(coordinates) // 2]
        return float(p[0]), float(p[1])
    if geom_type == "Polygon" and coordinates and coordinates[0]:
        p = coordinates[0][0]
        return float(p[0]), float(p[1])
    if geom_type == "MultiPolygon" and coordinates and coordinates[0] and coordinates[0][0]:
        p = coordinates[0][0][0]
        return float(p[0]), float(p[1])
    return None, None


def write_status(region_name: str) -> None:
    status = {
        "region": region_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "planet_file": str(SETTINGS.planet_path),
        "low_mbtiles": str(SETTINGS.low_tiles_path),
        "high_mbtiles": str(SETTINGS.high_tiles_path),
        "search_db": str(SETTINGS.search_db_path),
    }
    SETTINGS.status_path.write_text(json.dumps(status, indent=2) + "\n")


def build_all(force_planet_download: bool = False) -> None:
    ensure_dirs()
    with SETTINGS.lock_path.open("w") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        if force_planet_download and SETTINGS.planet_path.exists():
            SETTINGS.planet_path.unlink()

        _download_planet()
        _build_low_tiles()
        region = _build_high_extract()
        _build_high_tiles()
        _build_search_index()
        write_status(region["name"])


def maybe_build_on_startup() -> None:
    ensure_dirs()
    if not SETTINGS.startup_import:
        return
    required = [
        SETTINGS.low_tiles_path,
        SETTINGS.high_tiles_path,
        SETTINGS.search_db_path,
        SETTINGS.status_path,
    ]
    if all(path.exists() for path in required):
        return
    build_all(force_planet_download=False)


if __name__ == "__main__":
    force = os.getenv("FORCE_PLANET_REFRESH", "false").lower() in {"1", "true", "yes", "on"}
    build_all(force_planet_download=force)
