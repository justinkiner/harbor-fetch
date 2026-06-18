# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Harbor Fetch is a CLI tool that downloads JW.org publications in multiple languages and formats (PDF, EPUB, JWPUB). It reads language codes and publication symbols from YAML config files, queries the JW.org APIs, and saves files into organized directories.

## Commands

```bash
# Set up
python3 -m venv .venv
pip install -e .

# Run
harbor-fetch                          # download everything
harbor-fetch --dry-run                # preview without downloading
harbor-fetch -o /path/to/dir          # custom output directory
harbor-fetch --formats PDF            # restrict to specific formats
harbor-fetch --english-titles         # name files with English titles, not vernacular

# Also runnable as a module
python -m harbor_fetch
```

## Testing

```bash
pip install -e ".[dev]"   # installs pytest
pytest                    # run the full suite

# Useful subsets
pytest tests/test_api.py              # English-title lookups, fallbacks, caching
pytest tests/test_naming.py           # filename construction / sanitizing
pytest tests/test_cli_integration.py  # end-to-end main() over a mocked HTTP layer
```

Tests mock at the `requests.get` boundary, so the suite is fully offline and deterministic. The integration test runs `main()` in a temp directory with generated config files and asserts on the files written to disk.

## Configuration

- **`products.yaml`** — language codes and publication symbols for publication downloads. Top-level `languages` key holds language codes (e.g. `E`, `S`, `K`) using JW.org's own symbols (not ISO 639). Entry format for products: `symbol{:optional lang code}{:optional format}`. Examples: `nwt` (all languages, default formats), `jwlb:E` (English only, default formats), `jwlb::APK` (all languages, APK only), `jwlb:E:APK` (English only, APK only). When a format is specified it is the only value sent to the API; the global `--formats` flag is a post-fetch filter and does not affect the API call.
- **`videos.yaml`** — language codes and video series for video downloads. Top-level `languages` key holds language codes independently of publications.

Each config file has its own `languages` list, so publication and video downloads can target different sets of languages.

`languages.yaml` is no longer read and can be removed; it is kept only as a reference for available language codes.

`config.py:load_config()` reads `products.yaml` and returns `(languages, publications, default_formats)`.
`config.py:load_videos_config()` reads `videos.yaml` and returns a `VideoConfig` (which includes `.languages`).

## Package Structure

```
harbor_fetch/
  config.py      — load_config(): reads YAML files, returns (lang_codes, pub_symbols)
  api.py         — fetch_language_metadata(), fetch_pub_links(): JW.org API calls
  downloader.py  — download_file(url, dest): streaming download helper
  __main__.py    — CLI entry point (argparse, orchestration, progress output)
```

## APIs

### Language Data
```
GET https://www.jw.org/en/languages
```
Returns language metadata. The `langcode` field matches the codes in `languages.yaml`. The vernacular (native) name is in `vernacularName` (or `vernacular` / `name` as fallbacks).

### PubMedia — Download Links
```
GET https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS
  ?output=json&pub={symbol}&fileformat=PDF,EPUB,JWPUB
  &alllangs=0&langwritten={lang_code}&txtCMSLang={lang_code}
```
Response shape: `{"pubName": "...", "files": {"E": {"PDF": [...], "EPUB": [...], "JWPUB": [...]}}}`.
Each format list contains file objects with a top-level `url` field (or nested under `file.url`).
Only `file_list[0]` is used — the complete edition, not individual chapters.
`pubName` may contain HTML entities; `api.py` decodes them with `html.unescape`.

## Output Conventions

**Directory:** `{lang-code}-{english-name}` → `E-English`, `S-Spanish`, `K-Ukrainian`

**File:** `{pub-symbol}-{lang-code}-{vernacular-pub-name}.{ext}` → `nwt-E-New World Translation of the Holy Scriptures (2013 Revision).pdf`

Characters unsafe in filenames (`\ / : * ? " < > |`) are replaced with `_` by `_safe()` in `__main__.py`.

**English titles (`--english-titles`):** by default file names use the vernacular (langwritten) title. With this flag, names use the English title while the files themselves remain in the configured language. Because the API's `pubName` and per-track `title` fields always reflect `langwritten` (not `txtCMSLang`), the English title is obtained via a second query with `langwritten=E`: `api.py:fetch_pub_english_name(symbol, formats)` for publications and `api.py:fetch_video_english_titles(symbol, formats)` (returning `{track: title}`, matched to `VideoItem.track`) for videos. Both are `lru_cache`d and return `None`/`{}` on 404 or error so callers fall back to the vernacular title. The publication lookup reuses the publication's own format string — mixing incompatible formats (e.g. text with audio/video) makes the API return 400 for some publications.
