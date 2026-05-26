# Harbor Fetch

A command-line tool that downloads JW.org publications and videos in multiple languages. Configuration is driven by three YAML files; running the tool fetches everything configured and saves it into per-language directories.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
# Download everything configured
harbor-fetch

# Preview without writing any files
harbor-fetch --dry-run

# Write to a custom directory (default: downloads/)
harbor-fetch --output ~/Downloads/JW

# Override the download formats for this run only
harbor-fetch --formats PDF
harbor-fetch --formats PDF,EPUB
```

## Configuration

### `languages.yaml`

Lists the JW.org language codes to download for. Language codes are JW.org's own symbols, not ISO 639.

```yaml
languages:
  - E   # English
  - S   # Spanish
  - TG  # Tagalog
```

### `products.yaml`

Lists the publication symbols to download, with optional per-entry language and format overrides. Also defines the default download formats used when no override is specified and `--formats` is not passed on the command line.

```yaml
default:
  formats:
    - JWPUB
    - EPUB
    - PDF

products:
  - nwt               # all languages, default formats
  - jwlb:E:APK        # English only, APK only
  - lff::EPUB         # all languages, EPUB only
  - wcg:E             # English only, default formats
```

**Entry format:** `symbol{:optional language code}{:optional format}`

- Two segments → `symbol:lang` (English only, default formats)
- Three segments → `symbol:lang:format` (English only, that format only)
- Empty segment → use the default: `symbol::PDF` means all languages, PDF only

When a format is specified per-product, it is the only value sent to the API for that product. The `--formats` flag is a post-fetch filter and does not affect per-product overrides.

### `videos.yaml`

Lists video publication symbols to download, with an optional per-entry track filter. Also defines the default resolution and formats.

```yaml
defaults:
  resolution: 720p
  formats:
    - mp4

videos:
  - wsb             # all tracks
  - sjjm:1,3,5      # only tracks 1, 3, and 5
```

**Entry format:** `symbol{:track1,track2,...}`

Available resolutions: `240p`, `360p`, `480p`, `720p`.

## Output Structure

```
downloads/
  E-English/
    nwt-E-New World Translation of the Holy Scriptures (2013 Revision).pdf
    nwt-E-New World Translation of the Holy Scriptures (2013 Revision).epub
    wsb-E-720p-Why Study the Bible?.mp4
  S-Spanish/
    nwt-S-La Biblia. Traducción del Nuevo Mundo (revisión del 2019).pdf
    wsb-S-720p-¿Por qué estudiar la Biblia?.mp4
```

**Publication file naming:** `{symbol}-{lang}-{vernacular title}.{ext}`

**Video file naming:** `{symbol}-{lang}-{resolution}-{track title}.{ext}`

On re-runs, files are skipped if the local MD5 matches the checksum provided by the API. A message is printed for each skipped file. Publications unavailable in a given language print `Does not exist for {language}` rather than an error.
