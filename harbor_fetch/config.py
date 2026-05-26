"""Load language codes and publication symbols from YAML config files."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Publication:
    symbol: str
    lang_override: str | None    # restrict to this language code; None means all languages
    format_override: str | None  # e.g. "APK"; None means use the global --formats flag


@dataclass
class Video:
    symbol: str
    tracks: list[int] | None  # None means all tracks; [1, 3] means only tracks 1 and 3


@dataclass
class VideoConfig:
    videos: list[Video]
    default_formats: list[str]   # e.g. ["MP4", "M4V"]
    default_resolution: str      # e.g. "720p"


def _load_yaml_list(path: Path, key: str) -> list[str]:
    if not path.exists():
        return []
    with path.open() as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    items = data.get(key, []) if isinstance(data, dict) else data
    return [str(item).strip() for item in items if item]


def _parse_publication(entry: str) -> Publication:
    """Parse a products.yaml entry into a Publication.

    Format: publication-symbol{:optional language code}{:optional format}

    Supported forms:
      nwt          → all languages, default formats
      jwlb:E       → English only, default formats
      jwlb::APK    → all languages, APK only
      jwlb:E:APK   → English only, APK only
    """
    parts = [p.strip() for p in entry.split(":")]
    symbol = parts[0]
    lang_override = parts[1].upper() if len(parts) > 1 and parts[1] else None
    format_override = parts[2].upper() if len(parts) > 2 and parts[2] else None
    return Publication(symbol=symbol, lang_override=lang_override, format_override=format_override)


def load_config(base_dir: Path | None = None) -> tuple[list[str], list[Publication], list[str]]:
    """Return (language_codes, publications, default_formats) from YAML config files.

    Languages are read from languages.yaml. Publications and default formats are
    read from products.yaml. Both files are resolved relative to base_dir (defaults to cwd).
    """
    base = base_dir or Path.cwd()

    languages = _load_yaml_list(base / "languages.yaml", "languages")

    products_path = base / "products.yaml"
    products_data: dict = {}
    if products_path.exists():
        with products_path.open() as f:
            products_data = yaml.safe_load(f) or {}

    raw_products = products_data.get("products", []) if isinstance(products_data, dict) else products_data
    publications = [_parse_publication(str(e).strip()) for e in raw_products if e]

    raw_formats = (products_data.get("default", {}) or {}).get("formats", [])
    default_formats = [str(f).strip().upper() for f in raw_formats if f]

    return languages, publications, default_formats


def _parse_video(entry: str) -> Video:
    """Parse a videos.yaml entry into a Video.

    Supported forms:
      wsb          → all tracks
      wsb:1,3,5    → only tracks 1, 3, and 5
    """
    if ":" in entry:
        symbol, track_str = entry.split(":", 1)
        tracks = [int(t.strip()) for t in track_str.split(",") if t.strip().isdigit()]
        return Video(symbol=symbol.strip(), tracks=tracks or None)
    return Video(symbol=entry.strip(), tracks=None)


def load_videos_config(base_dir: Path | None = None) -> VideoConfig:
    """Return video entries and defaults from videos.yaml.

    videos.yaml structure:
        defaults:
          resolution: 720p
          formats:
            - MP4
            - M4V
        videos:
          - wsb
          - sjjm:1,3,5
    """
    base = base_dir or Path.cwd()
    videos_path = base / "videos.yaml"

    if not videos_path.exists():
        return VideoConfig(videos=[], default_formats=["MP4"], default_resolution="720p")

    with videos_path.open() as f:
        data = yaml.safe_load(f) or {}

    raw_videos = data.get("videos", []) if isinstance(data, dict) else []
    videos = [_parse_video(str(s).strip()) for s in raw_videos if s]

    defaults = (data.get("defaults", {}) or {})
    raw_formats = defaults.get("formats", ["MP4"])
    default_formats = [str(f).strip().upper() for f in raw_formats if f]
    default_resolution = str(defaults.get("resolution", "720p")).strip()

    return VideoConfig(videos=videos, default_formats=default_formats, default_resolution=default_resolution)
