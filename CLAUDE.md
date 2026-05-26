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

# Also runnable as a module
python -m harbor_fetch
```

## Configuration

- **`languages.yaml`** — list of language codes (e.g. `E`, `S`, `K`) using JW.org's own symbols (not ISO 639)
- **`products.yaml`** — list of publication symbols. Entry format: `symbol{:optional lang code}{:optional format}`. Examples: `nwt` (all languages, default formats), `jwlb:E` (English only, default formats), `jwlb::APK` (all languages, APK only), `jwlb:E:APK` (English only, APK only). When a format is specified it is the only value sent to the API; the global `--formats` flag is a post-fetch filter and does not affect the API call.

`config.py:load_config()` reads both files and returns `(languages, publications)`.

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
