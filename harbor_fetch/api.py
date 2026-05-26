"""JW.org API helpers for fetching language metadata and publication/video download links."""

from dataclasses import dataclass
from html import unescape

import requests

LANGUAGES_URL = "https://www.jw.org/en/languages"
PUBMEDIA_URL = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"


@dataclass
class LanguageInfo:
    code: str
    name: str        # English name
    vernacular: str  # Native (vernacular) name


@dataclass
class DownloadItem:
    pub_symbol: str
    lang_code: str
    pub_name: str        # Vernacular publication title, used in file names
    format: str          # "PDF", "EPUB", or "JWPUB"
    url: str
    checksum: str | None  # MD5 hex digest provided by the API, or None if absent


@dataclass
class VideoItem:
    symbol: str
    lang_code: str
    title: str           # Individual track title, used in file names
    resolution: str      # e.g. "720p"
    format: str          # e.g. "MP4"
    url: str
    checksum: str | None


def fetch_language_metadata(codes: list[str]) -> dict[str, LanguageInfo]:
    """Query the JW.org languages endpoint and return info for the requested codes.

    Returns a dict keyed by language code (e.g. "E", "S", "K").
    Codes not found in the API response are omitted from the result.
    """
    resp = requests.get(LANGUAGES_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Response is {"languages": [...]} or a bare list depending on the endpoint.
    lang_list: list[dict] = data.get("languages", data) if isinstance(data, dict) else data

    codes_upper = {c.upper() for c in codes}
    result: dict[str, LanguageInfo] = {}

    for lang in lang_list:
        code: str = lang.get("langcode", "")
        if code.upper() not in codes_upper:
            continue
        # Field names vary slightly across API versions — try the most common ones.
        vernacular: str = (
            lang.get("vernacularName")
            or lang.get("vernacular")
            or lang.get("name")
            or code
        )
        name: str = lang.get("name") or vernacular
        result[code] = LanguageInfo(code=code, name=name, vernacular=vernacular)

    return result


def fetch_pub_links(
    pub_symbol: str,
    lang_code: str,
    formats: str = "PDF,EPUB,JWPUB",
) -> list[DownloadItem]:
    """Return download items for every available format of a publication/language pair.

    The PubMedia API returns a structure like:
        {"pubName": "...", "files": {"E": {"PDF": [...], "EPUB": [...], "JWPUB": [...]}}}

    Each entry in a format list is a file object that may have a top-level "url"
    or a nested "file.url". Only the first entry per format is used (the
    standard/complete edition rather than individual chapters or parts).

    *formats* is the comma-separated list of formats to request from the API.
    """
    params = {
        "output": "json",
        "pub": pub_symbol,
        "fileformat": formats,
        "alllangs": "0",
        "langwritten": lang_code,
        "txtCMSLang": lang_code,
    }
    resp = requests.get(PUBMEDIA_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    pub_name: str = unescape(data.get("pubName") or data.get("title") or pub_symbol).strip()

    # Navigate to the per-format dict for this language.
    files_by_lang: dict = data.get("files", {})
    if lang_code in files_by_lang:
        files_by_format: dict = files_by_lang[lang_code]
    elif files_by_lang:
        files_by_format = next(iter(files_by_lang.values()))
    else:
        return []

    items: list[DownloadItem] = []
    for fmt, file_list in files_by_format.items():
        if not file_list:
            continue
        file_obj: dict = file_list[0]
        file_meta: dict = file_obj.get("file", {})
        url: str = file_obj.get("url") or file_meta.get("url", "")
        checksum: str | None = file_meta.get("checksum") or None
        if url:
            items.append(
                DownloadItem(
                    pub_symbol=pub_symbol,
                    lang_code=lang_code,
                    pub_name=pub_name,
                    format=fmt.upper(),
                    url=url,
                    checksum=checksum,
                )
            )

    return items


def fetch_video_links(
    symbol: str,
    lang_code: str,
    resolution: str,
    formats: str = "MP4",
    tracks: list[int] | None = None,
) -> list[VideoItem]:
    """Return one VideoItem per track at the requested resolution for a video publication.

    The PubMedia API returns every resolution for every track in a flat list.
    This function filters to the desired resolution (matched case-insensitively
    against the "label" field) and skips track=0 entries, which are ZIP bundles
    of all files rather than individual videos.

    If *tracks* is provided, only those track numbers are included.
    """
    params = {
        "output": "json",
        "pub": symbol,
        "fileformat": formats,
        "alllangs": "0",
        "langwritten": lang_code,
        "txtCMSLang": lang_code,
    }
    resp = requests.get(PUBMEDIA_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    files_by_lang: dict = data.get("files", {})
    if lang_code in files_by_lang:
        files_by_format: dict = files_by_lang[lang_code]
    elif files_by_lang:
        files_by_format = next(iter(files_by_lang.values()))
    else:
        return []

    target_res = resolution.lower()
    items: list[VideoItem] = []

    for fmt, file_list in files_by_format.items():
        for file_obj in file_list:
            track_num: int = file_obj.get("track", 0)
            # Skip track=0 — these are "Download All" ZIP bundles, not individual videos.
            if track_num == 0:
                continue
            # If a track filter is specified, skip tracks not in the list.
            if tracks is not None and track_num not in tracks:
                continue
            # Keep only entries matching the requested resolution.
            if file_obj.get("label", "").lower() != target_res:
                continue
            file_meta: dict = file_obj.get("file", {})
            url: str = file_obj.get("url") or file_meta.get("url", "")
            if not url:
                continue
            items.append(
                VideoItem(
                    symbol=symbol,
                    lang_code=lang_code,
                    title=unescape(file_obj.get("title", "")).strip(),
                    resolution=file_obj.get("label", resolution),
                    format=fmt.upper(),
                    url=url,
                    checksum=file_meta.get("checksum") or None,
                )
            )

    return items
