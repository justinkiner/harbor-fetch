# Harbor Fetch — Build Prompt

Build a Python CLI tool called `harbor-fetch` that downloads JW.org publications and videos in multiple languages. The tool is configuration-driven: three YAML files (provided below) specify what to download. No user interaction is required at runtime.

---

## Config files

### `languages.yaml`
```yaml
languages:
  - E   # JW.org language code (not ISO 639)
  - S
  - TG
```

### `products.yaml`
```yaml
default:
  formats:        # default formats sent to the API when no per-product override exists
    - JWPUB
    - EPUB
    - PDF

products:         # entry format: symbol{:optional lang}{:optional format}
  - nwt           # all languages, default formats
  - jwlb:E:APK    # English only, APK only
  - lff::EPUB     # all languages, EPUB only
  - wcg:E         # English only, default formats
```

### `videos.yaml`
```yaml
defaults:
  resolution: 720p          # one of: 240p, 360p, 480p, 720p
  formats:
    - mp4

videos:                     # entry format: symbol{:track1,track2,...}
  - wsb                     # all tracks
  - sjjm:1,3,5              # only tracks 1, 3, and 5
```

---

## APIs

### Language metadata
```
GET https://www.jw.org/en/languages
```
Response: `{"languages": [{"langcode": "E", "name": "English", "vernacularName": "English", ...}, ...]}`

Use this to resolve language codes to their English names (for directory naming) and to validate codes from `languages.yaml`.

### PubMedia — publications and videos
```
GET https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS
  ?output=json
  &pub={symbol}
  &fileformat={comma-separated formats}    # e.g. PDF,EPUB,JWPUB or MP4
  &alllangs=0
  &langwritten={lang-code}
  &txtCMSLang={lang-code}
```

**Publication response shape:**
```json
{
  "pubName": "Enjoy Life Forever!",
  "files": {
    "E": {
      "PDF":   [{"title": "...", "file": {"url": "...", "checksum": "<md5>"}, ...}],
      "EPUB":  [...],
      "JWPUB": [...]
    }
  }
}
```
For publications, take only `file_list[0]` per format (the complete edition, not individual chapters).
`pubName` may contain HTML entities — decode them.

**Video response shape:**
Same endpoint and structure. The format list contains one entry per track per resolution:
```json
{
  "files": {
    "E": {
      "MP4": [
        {"title": "Track title", "track": 1, "label": "720p", "file": {"url": "...", "checksum": "<md5>"}, ...},
        {"title": "Track title", "track": 1, "label": "480p", "file": {...}, ...},
        {"title": "Download All Files (ZIP)", "track": 0, "label": "720p", ...}
      ]
    }
  }
}
```
For videos: iterate all entries, filter to the desired resolution via `label` (case-insensitive), and skip `track == 0` entries (those are ZIP bundles).

A 404 from this endpoint means the publication/video doesn't exist for that language. Print `Does not exist for {English language name}` and continue — do not count it as an error.

---

## Behavior

### Products entry parsing — `symbol{:lang}{:format}`
- `nwt` → all languages, default formats from `products.yaml`
- `jwlb:E` → English only, default formats
- `lff::EPUB` → all languages, EPUB only
- `jwlb:E:APK` → English only, APK only

The format override is sent directly to the API as the `fileformat` parameter. The default formats from `products.yaml` are always sent as `fileformat` when no override is given. The `--formats` CLI flag is a post-fetch filter only and never modifies the API call.

### Videos entry parsing — `symbol{:track1,track2,...}`
- `wsb` → all tracks at the configured resolution
- `sjjm:1,3,5` → only tracks 1, 3, and 5

### Output directory and file naming
Directories: `{lang-code}-{English name}` → `E-English`, `TG-Tagalog`

Publication files: `{symbol}-{lang}-{pub vernacular title}.{ext}`
→ `nwt-E-New World Translation of the Holy Scriptures (2013 Revision).pdf`

Video files: `{symbol}-{lang}-{resolution}-{track title}.{ext}`
→ `wsb-E-720p-Why Study the Bible?.mp4`

Characters illegal in filenames on macOS/Windows (`\ / : * ? " < > |`) must be replaced with `_`.

### Checksum / skip logic
The API returns an MD5 hex digest in `file.checksum`. Before downloading, if the destination file already exists and the API provides a checksum, compute the local file's MD5 and compare. If they match, print `{filename} — already up to date` and skip the download.

---

## CLI flags

| Flag | Default | Description |
|---|---|---|
| `--output`, `-o` | `downloads/` | Destination root directory |
| `--formats` | from `products.yaml` | Comma-separated format filter (post-fetch, publications only) |
| `--dry-run` | off | Print what would be downloaded without writing files |

---

## Package structure

```
harbor_fetch/
  config.py      — load_config() → (languages, publications, default_formats)
                   load_videos_config() → VideoConfig
                   Publication(symbol, lang_override, format_override)
                   Video(symbol, tracks)
                   VideoConfig(videos, default_formats, default_resolution)
  api.py         — fetch_language_metadata(codes) → dict[code, LanguageInfo]
                   fetch_pub_links(symbol, lang, formats) → list[DownloadItem]
                   fetch_video_links(symbol, lang, resolution, formats, tracks) → list[VideoItem]
  downloader.py  — download_file(url, dest)   streaming 64 KB chunks
                   md5_of_file(path) → str
  __main__.py    — CLI entry point; publications loop then videos loop
pyproject.toml   — declares harbor-fetch console script entry point
languages.yaml
products.yaml
videos.yaml
```

Dependencies: `requests`, `pyyaml`. Requires Python 3.10+.
