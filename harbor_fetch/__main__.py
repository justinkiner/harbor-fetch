"""Harbor Fetch CLI — download JW.org publications and videos in multiple languages."""

import argparse
import sys
from pathlib import Path

from requests.exceptions import HTTPError

from harbor_fetch.api import (
    DownloadItem,
    VideoItem,
    fetch_language_metadata,
    fetch_pub_english_name,
    fetch_pub_links,
    fetch_video_english_titles,
    fetch_video_links,
)
from harbor_fetch.config import load_config, load_videos_config
from harbor_fetch.downloader import download_file, md5_of_file


# Characters forbidden in file/directory names on Windows and macOS/Linux.
_UNSAFE = set(r'\/:*?"<>|')


def _safe(name: str) -> str:
    """Replace filesystem-unsafe characters with underscores."""
    return "".join(c if c not in _UNSAFE else "_" for c in name)


def pub_filename(item: DownloadItem, english_title: str | None = None) -> str:
    """Build the on-disk filename for a publication download item.

    Uses *english_title* when provided (for --english-titles); otherwise falls
    back to the item's vernacular pub_name.
    """
    title = english_title or item.pub_name
    return _safe(f"{item.pub_symbol}-{item.lang_code}-{title}.{item.format.lower()}")


def video_filename(item: VideoItem, english_title: str | None = None) -> str:
    """Build the on-disk filename for a video download item.

    Uses *english_title* when provided (for --english-titles); otherwise falls
    back to the item's vernacular track title.
    """
    title = english_title or item.title
    return _safe(f"{item.symbol}-{item.lang_code}-{item.resolution}-{title}.{item.format.lower()}")


def _handle_file(
    dest: Path,
    url: str,
    checksum: str | None,
    dry_run: bool,
    counters: dict,
) -> None:
    """Dry-run print, checksum-skip, or download a single file. Updates *counters* in place."""
    filename = dest.name

    if dry_run:
        print(f"    [dry-run] {dest}")
        print(f"              {url}")
        return

    if dest.exists() and checksum and md5_of_file(dest) == checksum:
        print(f"    {filename} — already up to date")
        counters["skipped"] += 1
        return

    print(f"    {filename} ... ", end="", flush=True)
    try:
        download_file(url, dest)
        print("OK")
        counters["downloaded"] += 1
    except Exception as exc:
        print(f"FAILED — {exc}")
        counters["errors"] += 1


def _http_error_message(exc: HTTPError, lang_name: str) -> tuple[str, bool]:
    """Return (message, is_error) for an HTTPError. 404s are not counted as errors."""
    if exc.response is not None and exc.response.status_code == 404:
        return f"Does not exist for {lang_name}", False
    return f"FETCH ERROR — {exc}", True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download JW.org publications and videos in multiple languages.",
    )
    parser.add_argument(
        "--output", "-o",
        default="downloads",
        metavar="DIR",
        help="Destination directory (default: downloads/)",
    )
    parser.add_argument(
        "--formats",
        default=None,
        metavar="FMT",
        help="Comma-separated list of formats to fetch (default: from products.yaml default.formats)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without writing any files",
    )
    parser.add_argument(
        "--english-titles",
        action="store_true",
        help=(
            "Name saved files using each item's English title instead of the "
            "vernacular title (falls back to the vernacular title when no "
            "English edition exists). Default: vernacular titles."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--only-products",
        action="store_true",
        help="Download publications only; ignore videos.yaml",
    )
    mode_group.add_argument(
        "--only-videos",
        action="store_true",
        help="Download videos only; ignore products.yaml",
    )
    args = parser.parse_args()

    # ── Config ────────────────────────────────────────────────────────────────
    pub_languages, publications, default_formats = load_config()
    video_cfg = load_videos_config()

    if args.only_videos:
        publications = []
        pub_languages = []
    elif args.only_products:
        video_cfg = video_cfg.__class__(
            languages=[], videos=[],
            default_formats=video_cfg.default_formats,
            default_resolution=video_cfg.default_resolution,
        )

    if not pub_languages and not video_cfg.languages:
        sys.exit("Error: no language codes found in products.yaml or videos.yaml")
    if not publications and not video_cfg.videos:
        sys.exit("Error: no publications found in products.yaml and no videos found in videos.yaml")
    if publications and not default_formats:
        sys.exit("Error: no default formats found in products.yaml under default.formats")

    # --formats overrides the yaml default; otherwise use what products.yaml specifies.
    default_fmt_str = ",".join(default_formats)
    wanted_formats = (
        {f.strip().upper() for f in args.formats.split(",")}
        if args.formats
        else set(default_formats)
    )

    if publications:
        pub_labels = []
        for p in publications:
            base = f"{p.symbol}-{p.issue}" if p.issue else p.symbol
            if p.lang_override or p.format_override:
                pub_labels.append(f"{base}:{p.lang_override or ''}:{p.format_override or ''}")
            else:
                pub_labels.append(base)
        print(f"Pub languages: {', '.join(pub_languages)}")
        print(f"Publications : {', '.join(pub_labels)}")
        print(f"Formats      : {', '.join(sorted(wanted_formats))}")

    if video_cfg.videos:
        video_labels = [
            f"{v.symbol}:{','.join(str(t) for t in v.tracks)}" if v.tracks else v.symbol
            for v in video_cfg.videos
        ]
        print(f"Vid languages: {', '.join(video_cfg.languages)}")
        print(f"Videos       : {', '.join(video_labels)}")
        print(f"Resolution   : {video_cfg.default_resolution}")

    print()

    # ── Language metadata ─────────────────────────────────────────────────────
    all_languages = list(dict.fromkeys(pub_languages + video_cfg.languages))
    print("Fetching language metadata from JW.org...")
    try:
        lang_meta = fetch_language_metadata(all_languages)
    except Exception as exc:
        sys.exit(f"Error fetching language metadata: {exc}")

    unknown = [c for c in all_languages if c not in lang_meta]
    if unknown:
        print(f"Warning: language codes not found in JW.org API (skipping): {', '.join(unknown)}")

    output_dir = Path(args.output)
    counters = {"downloaded": 0, "skipped": 0, "errors": 0}

    # ── Publications ──────────────────────────────────────────────────────────
    if publications:
        for lang_code in pub_languages:
            if lang_code not in lang_meta:
                continue

            info = lang_meta[lang_code]
            lang_dir = output_dir / _safe(f"{lang_code}-{info.name}")

            print(f"=== {lang_dir.name} ===")

            for pub in publications:
                if pub.lang_override and pub.lang_override != lang_code:
                    continue

                pub_label = f"{pub.symbol}-{pub.issue}" if pub.issue else pub.symbol
                print(f"  {pub_label}: ", end="", flush=True)

                api_formats = pub.format_override or default_fmt_str
                active_formats = {pub.format_override} if pub.format_override else wanted_formats

                try:
                    items = fetch_pub_links(pub.symbol, lang_code, formats=api_formats, issue=pub.issue)
                except HTTPError as exc:
                    msg, is_err = _http_error_message(exc, info.name)
                    print(msg)
                    if is_err:
                        counters["errors"] += 1
                    continue
                except Exception as exc:
                    print(f"FETCH ERROR — {exc}")
                    counters["errors"] += 1
                    continue

                items = [i for i in items if i.format in active_formats]

                if not items:
                    print("no matching files found")
                    continue

                print(f"{len(items)} file(s)")

                # All editions of a publication share one title; resolve the
                # English name once and fall back to the vernacular pubName.
                pub_title = None
                if args.english_titles:
                    pub_title = fetch_pub_english_name(pub.symbol, api_formats, pub.issue)

                for item in items:
                    filename = pub_filename(item, pub_title)
                    _handle_file(lang_dir / filename, item.url, item.checksum, args.dry_run, counters)

            print()

    # ── Videos ───────────────────────────────────────────────────────────────
    if video_cfg.videos:
        video_fmt_str = ",".join(video_cfg.default_formats)

        for lang_code in video_cfg.languages:
            if lang_code not in lang_meta:
                continue

            info = lang_meta[lang_code]
            lang_dir = output_dir / _safe(f"{lang_code}-{info.name}")

            print(f"=== {lang_dir.name} (videos) ===")

            for video in video_cfg.videos:
                track_label = f"tracks {','.join(str(t) for t in video.tracks)}" if video.tracks else "all tracks"
                print(f"  {video.symbol} [{video_cfg.default_resolution}, {track_label}]: ", end="", flush=True)

                try:
                    items = fetch_video_links(
                        video.symbol, lang_code,
                        resolution=video_cfg.default_resolution,
                        formats=video_fmt_str,
                        tracks=video.tracks,
                        docid=video.docid,
                    )
                except HTTPError as exc:
                    msg, is_err = _http_error_message(exc, info.name)
                    print(msg)
                    if is_err:
                        counters["errors"] += 1
                    continue
                except Exception as exc:
                    print(f"FETCH ERROR — {exc}")
                    counters["errors"] += 1
                    continue

                if not items:
                    print("no matching files found")
                    continue

                print(f"{len(items)} file(s)")

                # Map track number -> English title; fall back per track to the
                # vernacular title when no English edition/track exists.
                english_titles = {}
                if args.english_titles:
                    english_titles = fetch_video_english_titles(video.symbol, video_fmt_str, video.docid)

                for item in items:
                    filename = video_filename(item, english_titles.get(item.track))
                    _handle_file(lang_dir / filename, item.url, item.checksum, args.dry_run, counters)

            print()

    # ── Summary ───────────────────────────────────────────────────────────────
    if args.dry_run:
        print("Dry run complete — no files written.")
    else:
        print(
            f"Done: {counters['downloaded']} downloaded, "
            f"{counters['skipped']} already up to date, "
            f"{counters['errors']} error(s)."
        )
        if counters["downloaded"]:
            print(f"Saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
