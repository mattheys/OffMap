from __future__ import annotations

import json
from pathlib import Path


REGION_FILE = Path(__file__).resolve().parent / "data" / "regions.json"

SYNONYMS = {
    "bavaria": "bayern",
    "cologne": "koln",
    "north rhine westphalia": "nordrhein-westfalen",
    "saxony": "sachsen",
    "thuringia": "thueringen",
    "franconia": "franken",
}


def load_regions() -> list[dict]:
    with REGION_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def resolve_region(name: str) -> dict:
    target = _norm(name)
    target = _norm(SYNONYMS.get(target, target))
    regions = load_regions()
    for region in regions:
        aliases = region.get("aliases", [])
        if any(_norm(alias) == target for alias in aliases):
            return region
        if _norm(region.get("name", "")) == target:
            return region
    known = ", ".join(region["name"] for region in regions[:20])
    raise ValueError(f"Unknown region '{name}'. Examples: {known} ...")
