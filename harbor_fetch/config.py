"""Load language codes and publication symbols from YAML config files."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_PERIODICAL_RE = re.compile(r'^([A-Za-z]+)-(\d+)$')


@dataclass
class Publication:
    symbol: str
    lang_override: str | None    # restrict to this language code; None means all languages
    format_override: str | None  # e.g. "APK"; None means use the global --formats flag
    issue: str | None = None     # e.g. "202011" for periodicals like g-202011


@dataclass
class Video:
    symbol: str               # publication symbol, or string form of the docid
    tracks: list[int] | None  # None means all tracks; [1, 3] means only tracks 1 and 3
    docid: int | None = None  # set when the entry is a numeric document ID


@dataclass
class VideoConfig:
    languages: list[str]
    videos: list[Video]
    default_formats: list[str]   # e.g. ["MP4", "M4V"]
    default_resolution: str      # e.g. "720p"


def _read_lang_list(data: dict) -> list[str]:
    raw = (data.get("languages") or []) if isinstance(data, dict) else []
    return [str(item).strip() for item in raw if item]


def _parse_publication(entry: str) -> Publication:
    """Parse a products.yaml entry into a Publication.

    Format: publication-symbol{:optional language code}{:optional format}

    Supported forms:
      nwt          → all languages, default formats
      jwlb:E       → English only, default formats
      jwlb::APK    → all languages, APK only
      jwlb:E:APK   → English only, APK only
      g-202011     → periodical: symbol=g, issue=202011, all languages, default formats
      g-202011:E   → periodical: English only
    """
    parts = [p.strip() for p in entry.split(":")]
    raw_symbol = parts[0]
    lang_override = parts[1].upper() if len(parts) > 1 and parts[1] else None
    format_override = parts[2].upper() if len(parts) > 2 and parts[2] else None

    m = _PERIODICAL_RE.match(raw_symbol)
    if m:
        symbol, issue = m.group(1), m.group(2)
    else:
        symbol, issue = raw_symbol, None

    return Publication(symbol=symbol, lang_override=lang_override, format_override=format_override, issue=issue)


def load_config(base_dir: Path | None = None) -> tuple[list[str], list[Publication], list[str]]:
    """Return (language_codes, publications, default_formats) from products.yaml."""
    base = base_dir or Path.cwd()

    products_path = base / "products.yaml"
    products_data: dict = {}
    if products_path.exists():
        with products_path.open() as f:
            products_data = yaml.safe_load(f) or {}

    languages = _read_lang_list(products_data)

    raw_products = (products_data.get("products") or []) if isinstance(products_data, dict) else (products_data or [])
    publications = [_parse_publication(str(e).strip()) for e in raw_products if e]

    raw_formats = ((products_data.get("default") or {}).get("formats") or [])
    default_formats = [str(f).strip().upper() for f in raw_formats if f]

    return languages, publications, default_formats


def _parse_video(entry: str) -> Video:
    """Parse a videos.yaml entry into a Video.

    Supported forms:
      wsb          → all tracks (symbol-based)
      wsb:1,3,5    → only tracks 1, 3, and 5 (symbol-based)
      502014331    → all tracks (docid-based)
      502014331:2  → track 2 only (docid-based)
    """
    if ":" in entry:
        symbol, track_str = entry.split(":", 1)
        tracks = [int(t.strip()) for t in track_str.split(",") if t.strip().isdigit()]
    else:
        symbol, tracks = entry, None

    symbol = symbol.strip()
    docid = int(symbol) if symbol.isdigit() else None
    return Video(symbol=symbol, tracks=tracks or None, docid=docid)


def load_videos_config(base_dir: Path | None = None) -> VideoConfig:
    """Return video entries and defaults from videos.yaml.

    videos.yaml structure:
        languages:
          - E
          - S
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
        return VideoConfig(languages=[], videos=[], default_formats=["MP4"], default_resolution="720p")

    with videos_path.open() as f:
        data = yaml.safe_load(f) or {}

    languages = _read_lang_list(data)
    raw_videos = (data.get("videos") or []) if isinstance(data, dict) else []
    videos = [_parse_video(str(s).strip()) for s in raw_videos if s]

    defaults = (data.get("defaults") or {})
    raw_formats = defaults.get("formats") or ["MP4"]
    default_formats = [str(f).strip().upper() for f in raw_formats if f]
    default_resolution = str(defaults.get("resolution", "720p")).strip()

    return VideoConfig(
        languages=languages,
        videos=videos,
        default_formats=default_formats,
        default_resolution=default_resolution,
    )
