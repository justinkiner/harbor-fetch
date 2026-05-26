"""Harbor Fetch CLI — download JW.org publications in multiple languages."""

import argparse
import sys
from pathlib import Path

from requests.exceptions import HTTPError

from harbor_fetch.api import fetch_language_metadata, fetch_pub_links
from harbor_fetch.config import load_config
from harbor_fetch.downloader import download_file, md5_of_file


# Characters forbidden in file/directory names on Windows and macOS/Linux.
_UNSAFE = set(r'\/:*?"<>|')


def _safe(name: str) -> str:
    """Replace filesystem-unsafe characters with underscores."""
    return "".join(c if c not in _UNSAFE else "_" for c in name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download JW.org publications in multiple languages and formats.",
    )
    parser.add_argument(
        "--output", "-o",
        default="downloads",
        metavar="DIR",
        help="Destination directory (default: downloads/)",
    )
    parser.add_argument(
        "--formats",
        default="PDF,EPUB,JWPUB",
        metavar="FMT",
        help="Comma-separated list of formats to fetch (default: PDF,EPUB,JWPUB)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without writing any files",
    )
    args = parser.parse_args()

    wanted_formats = {f.strip().upper() for f in args.formats.split(",")}

    # ── Config ────────────────────────────────────────────────────────────────
    languages, publications = load_config()

    if not languages:
        sys.exit("Error: no language codes found in languages.yaml")
    if not publications:
        sys.exit("Error: no publication symbols found in products.yaml")

    pub_labels = []
    for p in publications:
        if p.lang_override or p.format_override:
            pub_labels.append(
                f"{p.symbol}:{p.lang_override or ''}:{p.format_override or ''}"
            )
        else:
            pub_labels.append(p.symbol)
    print(f"Languages    : {', '.join(languages)}")
    print(f"Publications : {', '.join(pub_labels)}")
    print(f"Formats      : {', '.join(sorted(wanted_formats))}")
    print()

    # ── Language metadata ─────────────────────────────────────────────────────
    print("Fetching language metadata from JW.org...")
    try:
        lang_meta = fetch_language_metadata(languages)
    except Exception as exc:
        sys.exit(f"Error fetching language metadata: {exc}")

    unknown = [c for c in languages if c not in lang_meta]
    if unknown:
        print(f"Warning: language codes not found in JW.org API (skipping): {', '.join(unknown)}")

    output_dir = Path(args.output)
    downloaded = 0
    skipped = 0
    errors = 0

    # ── Download loop ─────────────────────────────────────────────────────────
    for lang_code in languages:
        if lang_code not in lang_meta:
            continue

        info = lang_meta[lang_code]
        dir_name = _safe(f"{lang_code}-{info.name}")
        lang_dir = output_dir / dir_name

        print(f"=== {dir_name} ===")

        for pub in publications:
            # Skip if this publication is restricted to a different language.
            if pub.lang_override and pub.lang_override != lang_code:
                continue

            print(f"  {pub.symbol}: ", end="", flush=True)

            # The API always receives either the product's format override or the
            # canonical default. The --formats flag is a post-fetch filter only.
            api_formats = pub.format_override or "PDF,EPUB,JWPUB"
            active_formats = {pub.format_override} if pub.format_override else wanted_formats

            try:
                items = fetch_pub_links(pub.symbol, lang_code, formats=api_formats)
            except HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    print(f"Does not exist for {info.name}")
                else:
                    print(f"FETCH ERROR — {exc}")
                    errors += 1
                continue
            except Exception as exc:
                print(f"FETCH ERROR — {exc}")
                errors += 1
                continue

            items = [i for i in items if i.format in active_formats]

            if not items:
                print("no matching files found")
                continue

            print(f"{len(items)} file(s)")

            for item in items:
                ext = item.format.lower()
                filename = _safe(f"{item.pub_symbol}-{item.lang_code}-{item.pub_name}.{ext}")
                dest = lang_dir / filename

                if args.dry_run:
                    print(f"    [dry-run] {dest}")
                    print(f"              {item.url}")
                    continue

                # Skip if the file already exists and its MD5 matches the API checksum.
                if dest.exists() and item.checksum:
                    if md5_of_file(dest) == item.checksum:
                        print(f"    {filename} — already up to date")
                        skipped += 1
                        continue

                print(f"    {filename} ... ", end="", flush=True)
                try:
                    download_file(item.url, dest)
                    print("OK")
                    downloaded += 1
                except Exception as exc:
                    print(f"FAILED — {exc}")
                    errors += 1

        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    if args.dry_run:
        print("Dry run complete — no files written.")
    else:
        print(f"Done: {downloaded} downloaded, {skipped} already up to date, {errors} error(s).")
        if downloaded:
            print(f"Saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
