#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.request import urlopen

INDEX_URL = "https://download.geofabrik.de/index-v1.json"


def _slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


def _bbox_from_coords(coords, current=None):
    if current is None:
        current = [180.0, 90.0, -180.0, -90.0]
    if isinstance(coords, list) and coords and isinstance(coords[0], (float, int)) and len(coords) >= 2:
        lon = float(coords[0])
        lat = float(coords[1])
        current[0] = min(current[0], lon)
        current[1] = min(current[1], lat)
        current[2] = max(current[2], lon)
        current[3] = max(current[3], lat)
        return current
    if isinstance(coords, list):
        for item in coords:
            _bbox_from_coords(item, current)
    return current


def _value_to_str(value) -> str:
    if isinstance(value, list):
        return ",".join(str(v) for v in value if v)
    if value is None:
        return ""
    return str(value)


def _path_aliases(value: str) -> set[str]:
    aliases = set()
    if "/" not in value:
        return aliases
    parts = [p for p in value.split("/") if p]
    for part in parts:
        aliases.add(part)
        aliases.add(part.replace("-", " "))
        aliases.add(part.replace("_", " "))
    aliases.add(parts[-1].replace("-", " "))
    return {a.strip() for a in aliases if a.strip()}


def _iso_value(entry: dict) -> str:
    return entry["iso3166_2"] or entry["iso3166_1_alpha2"] or "-"


def _build_tree(entries: list[dict]) -> dict:
    root: dict = {"children": {}, "entries": []}
    for entry in entries:
        node = root
        for part in entry.get("parents") or []:
            children = node["children"]
            if part not in children:
                children[part] = {"children": {}, "entries": []}
            node = children[part]
        node["entries"].append(entry)
    return root


def _render_tree(node: dict, lines: list[str], depth: int = 0) -> None:
    indent = "  " * depth
    child_names = sorted(node["children"], key=lambda value: value.lower())
    for child_name in child_names:
        lines.append(f"{indent}- **`{child_name}/`**")
        _render_tree(node["children"][child_name], lines, depth + 1)

    node_entries = sorted(node["entries"], key=lambda entry: entry["name"].lower())
    for entry in node_entries:
        iso = _iso_value(entry)
        if iso == "-":
            lines.append(f"{indent}- {entry['name']} (`{entry['id']}`)")
        else:
            lines.append(f"{indent}- {entry['name']} (`{iso}`, `{entry['id']}`)")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "offmap" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    regions_md = repo_root / "REGIONS.md"
    regions_json = data_dir / "regions.json"

    with urlopen(INDEX_URL) as response:
        payload = json.load(response)

    features = payload.get("features", [])
    out = []

    for feature in features:
        props = feature.get("properties", {})
        name = (props.get("name") or "").strip()
        if not name:
            continue
        urls = props.get("urls", {})
        pbf_url = urls.get("pbf", "")
        geometry = feature.get("geometry")
        if not geometry:
            continue
        bbox = _bbox_from_coords(geometry.get("coordinates"))
        if bbox[0] == 180.0 and bbox[2] == -180.0:
            continue
        parents = props.get("parents") or []
        parent = props.get("parent")
        if parent and parent not in parents:
            parents.append(parent)
        entry = {
            "id": props.get("id") or _slug(name),
            "name": name,
            "slug": _slug(name),
            "iso3166_1_alpha2": _value_to_str(props.get("iso3166-1:alpha2")),
            "iso3166_2": _value_to_str(props.get("iso3166-2")),
            "parents": [p for p in parents if isinstance(p, str)],
            "bbox": bbox,
            "pbf_url": pbf_url,
        }
        aliases = {name, entry["slug"], entry["id"]}
        if entry["iso3166_2"]:
            aliases.add(entry["iso3166_2"])
        if entry["iso3166_1_alpha2"]:
            aliases.add(entry["iso3166_1_alpha2"])
        aliases.update(_path_aliases(name))
        aliases.update(_path_aliases(entry["id"]))
        entry["aliases"] = sorted(a for a in aliases if a)
        out.append(entry)

    out.sort(key=lambda x: x["name"].lower())
    regions_json.write_text(json.dumps(out, indent=2) + "\n")

    lines = [
        "# Supported Regions",
        "",
        "This list is auto-generated from Geofabrik's region index and is accepted by `HIGH_DETAIL_REGION`.",
        "",
        "Accepted value forms: region name, region id/slug, and ISO code (when available).",
        "",
        f"Total regions: **{len(out)}**",
        "",
        "## Region Tree",
        "",
        "Tree branches are parent paths from Geofabrik. Leaves are selectable regions.",
        "",
    ]
    _render_tree(_build_tree(out), lines)

    regions_md.write_text("\n".join(lines) + "\n")
    print(f"Wrote {regions_json}")
    print(f"Wrote {regions_md}")


if __name__ == "__main__":
    main()
