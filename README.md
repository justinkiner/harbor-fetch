# Harbor Fetch

A command-line tool that downloads JW.org publications and videos in multiple languages. Configuration is driven by two YAML files (`products.yaml` and `videos.yaml`); running the tool fetches everything configured and saves it into per-language directories.

## Setup

### Windows

1. Go to the [Releases page](https://github.com/justinkiner/harbor-fetch/releases/latest) and download `harbor-fetch.exe`.
2. Create a folder for your work (e.g. `C:\Users\You\harbor-fetch`).
3. Move `harbor-fetch.exe` into that folder.
4. Download `products.yaml` and `videos.yaml` from this repository and place them in the same folder. Edit them to configure which languages and publications you want.
5. Open **Command Prompt**, navigate to your folder, and run:

```cmd
harbor-fetch.exe
```

To open Command Prompt in a specific folder: open the folder in File Explorer, click the address bar, type `cmd`, and press Enter.

### macOS

Requires Python 3.10 or later. Check your version with `python3 --version`; if needed, download Python from [python.org](https://www.python.org/downloads/).

1. Download or clone this repository.
2. Open **Terminal** and navigate to the repository folder.
3. Create a virtual environment, activate it, and install the tool:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

4. Run the tool:

```bash
harbor-fetch
```

> **Note:** You must activate the virtual environment (`source .venv/bin/activate`) each time you open a new Terminal window before running `harbor-fetch`.

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

# Name saved files using English titles instead of vernacular titles
harbor-fetch --english-titles
```

On Windows, replace `harbor-fetch` with `harbor-fetch.exe` in any command above.

## Configuration

Each config file carries its own language list, so publication and video downloads can target independent sets of languages.

### `products.yaml`

Defines the languages, default formats, and publication symbols for publication downloads.

```yaml
languages:
  - E   # English
  - S   # Spanish
  - TG  # Tagalog

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

**Product entry format:** `symbol{:optional language code}{:optional format}`

- Two segments → `symbol:lang` (that language only, default formats)
- Three segments → `symbol:lang:format` (that language only, that format only)
- Empty middle segment → `symbol::PDF` means all languages, PDF only

When a format is specified per-product, it is the only value sent to the API for that product. The `--formats` flag is a post-fetch filter and does not affect per-product overrides.

### `videos.yaml`

Defines the languages, default resolution and formats, and video series for video downloads.

```yaml
languages:
  - E   # English
  - S   # Spanish

defaults:
  resolution: 720p
  formats:
    - mp4

videos:
  - wsb             # all tracks
  - sjjm:1,3,5      # only tracks 1, 3, and 5
```

**Video entry format:** `symbol{:track1,track2,...}`

Available resolutions: `240p`, `360p`, `480p`, `720p`.

Language codes in both files use JW.org's own symbols, not ISO 639 (e.g. `E` for English, `S` for Spanish, `TG` for Tagalog).

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

By default, files are named with the vernacular (native-language) title. Pass `--english-titles` to use each item's English title instead, while still downloading the files in the configured language. When a publication or video has no English edition, the vernacular title is used as a fallback.

On re-runs, files are skipped if the local MD5 matches the checksum provided by the API. A message is printed for each skipped file. Publications unavailable in a given language print `Does not exist for {language}` rather than an error.
