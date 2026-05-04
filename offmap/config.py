from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "/data"))
    region: str = os.getenv("HIGH_DETAIL_REGION", "Germany")
    planet_url: str = os.getenv(
        "PLANET_URL", "https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf"
    )
    low_max_zoom: int = int(os.getenv("LOW_MAX_ZOOM", "8"))
    high_max_zoom: int = int(os.getenv("HIGH_MAX_ZOOM", "14"))
    tile_threads: int = int(os.getenv("TILE_THREADS", "1"))
    auto_update: bool = _env_bool("AUTO_UPDATE", True)
    update_cron: str = os.getenv("UPDATE_CRON", "0 3 1 * *")
    planet_max_age_days: int = int(os.getenv("PLANET_MAX_AGE_DAYS", "30"))
    startup_import: bool = _env_bool("STARTUP_IMPORT", True)
    tilemaker_config_path: str = os.getenv(
        "TILEMAKER_CONFIG_PATH", "/app/tilemaker/config-openmaptiles.json"
    )
    tilemaker_process_path: str = os.getenv(
        "TILEMAKER_PROCESS_PATH", "/app/tilemaker/process-openmaptiles.lua"
    )

    @property
    def planet_dir(self) -> Path:
        return self.data_dir / "planet"

    @property
    def tiles_dir(self) -> Path:
        return self.data_dir / "tiles"

    @property
    def search_dir(self) -> Path:
        return self.data_dir / "search"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def planet_path(self) -> Path:
        return self.planet_dir / "planet.osm.pbf"

    @property
    def region_extract_path(self) -> Path:
        return self.state_dir / "high_detail.osm.pbf"

    @property
    def low_tiles_path(self) -> Path:
        return self.tiles_dir / "low.mbtiles"

    @property
    def high_tiles_path(self) -> Path:
        return self.tiles_dir / "high.mbtiles"

    @property
    def search_db_path(self) -> Path:
        return self.search_dir / "search.db"

    @property
    def lock_path(self) -> Path:
        return self.state_dir / "update.lock"

    @property
    def status_path(self) -> Path:
        return self.state_dir / "status.json"

    @property
    def planet_max_age(self) -> timedelta:
        return timedelta(days=max(self.planet_max_age_days, 0))


SETTINGS = Settings()


def ensure_dirs(settings: Settings = SETTINGS) -> None:
    settings.planet_dir.mkdir(parents=True, exist_ok=True)
    settings.tiles_dir.mkdir(parents=True, exist_ok=True)
    settings.search_dir.mkdir(parents=True, exist_ok=True)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
