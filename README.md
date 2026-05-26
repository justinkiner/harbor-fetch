# Harbor Fetch

This is a simple tool to fetch downloadable publications for use in the Harbor Ministry. Given a
list of languages codes (e.g. "E", "TG", "K") and publication symbols (e.g. "nwt", "lffi") it will
fetch the publications from the JW.org website and save them to a specified directory.

Directories are named with language symbol first followed by the language name (e.g. "E-English",
"TG-Tagalog", "K-Ukrainian"). Publication files are downloaded in to these folders, named with the
publication symbol, language symbol, and the vernacular publication name (e.g. "nwt-E-New World
Translation of the Holy Scriptures.pdf", "lffi-E-Enjoy Life Forever.pdf").

Two API's are used to fetch this data:

- Language Data: `https://www.jw.org/en/languages`
- Download information (PubMedia API):
  `https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS?output=json&pub={publication-symbol}&fileformat=PDF%2CEPUB%2CJWPUB&alllangs=0&langwritten={language-code}&txtCMSLang={language-code}`

Specify the languages in the `languages.yaml` file, one language code per line. Specify the
publications in the `products.yaml` file, one publication symbol per line. The program will
fetch the available formats (EPUB, JWPUB, PDF) for each publication and download them to the
specified directory.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
# Download all publications for all configured languages
harbor-fetch

# Preview what would be downloaded without writing any files
harbor-fetch --dry-run

# Download to a custom directory
harbor-fetch --output ~/Downloads/JW

# Download specific formats only
harbor-fetch --formats PDF
harbor-fetch --formats PDF,EPUB
```

Files are saved under the output directory (default: `downloads/`) in per-language subdirectories.
