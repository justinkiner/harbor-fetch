"""Load language codes and publication symbols from YAML config files."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Publication:
    symbol: str
    lang_override: str | None    # restrict to this language code; None means all languages
    format_override: str | None  # e.g. "APK"; None means use the global --formats flag


def _load_yaml_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open() as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    return [str(item).strip() for item in data if item]


def _parse_publication(entry: str) -> Publication:
    """Parse a products.yaml entry into a Publication.

    Format: publication-symbol{:optional language code}{:optional format}

    Supported forms:
      nwt          → all languages, default formats (PDF,EPUB,JWPUB)
      jwlb:E       → English only, default formats
      jwlb::APK    → all languages, APK only
      jwlb:E:APK   → English only, APK only
    """
    parts = [p.strip() for p in entry.split(":")]
    symbol = parts[0]
    lang_override = parts[1].upper() if len(parts) > 1 and parts[1] else None
    format_override = parts[2].upper() if len(parts) > 2 and parts[2] else None
    return Publication(symbol=symbol, lang_override=lang_override, format_override=format_override)


def load_config(base_dir: Path | None = None) -> tuple[list[str], list[Publication]]:
    """Return (language_codes, publications) from YAML config files.

    Languages are read from languages.yaml. Publications are read from
    products.yaml. Both files are resolved relative to base_dir (defaults to cwd).
    """
    base = base_dir or Path.cwd()

    languages = _load_yaml_list(base / "languages.yaml")
    publications = [_parse_publication(e) for e in _load_yaml_list(base / "products.yaml")]

    return languages, publications
