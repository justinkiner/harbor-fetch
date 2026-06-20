"""End-to-end integration test for the harbor-fetch CLI.

Runs ``main()`` exactly as a user would, mocking only the true external
boundary — ``requests.get`` — so that config loading, the API layer, filename
selection (vernacular vs. ``--english-titles``), the real streaming download,
on-disk writes, checksum-based skipping, and the summary output all execute for
real against fake HTTP responses.

Both ``harbor_fetch.api`` and ``harbor_fetch.downloader`` reference the same
``requests`` module object, so patching ``requests.get`` once covers every
network call the run makes.
"""

import hashlib
import sys

import pytest
import requests

from harbor_fetch import api
from harbor_fetch.__main__ import main


# ── Fake HTTP layer ───────────────────────────────────────────────────────────

# Bytes served for each download URL. Their MD5s are embedded as the API
# "checksum" so the real checksum-skip path can be exercised on a re-run.
NWT_S_URL = "http://files.example/nwt_S.epub"
SJJM_S_URL = "http://files.example/sjjm_S_1_720p.mp4"
DOCID_S_URL = "http://files.example/docid_502014331_S_1_720p.mp4"
G_202011_S_URL = "http://files.example/g_202011_S.epub"
FILE_BODIES = {
    NWT_S_URL: b"SPANISH-NWT-EPUB-CONTENT",
    SJJM_S_URL: b"SPANISH-SJJM-TRACK1-720P-CONTENT",
    DOCID_S_URL: b"SPANISH-DOCID-TRACK1-720P-CONTENT",
    G_202011_S_URL: b"SPANISH-AWAKE-202011-EPUB-CONTENT",
}


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


_LANGUAGES = {
    "languages": [
        {"langcode": "S", "name": "Spanish", "vernacularName": "español"},
        {"langcode": "E", "name": "English", "vernacularName": "English"},
    ]
}

# PubMedia responses keyed by (identifier, issue, langwritten).
# identifier is the pub symbol (str) or docid (int); issue is None for
# non-periodicals. The vernacular (S) entries carry real download URLs +
# checksums; the English (E) entries supply titles for --english-titles lookups.
_PUBMEDIA = {
    ("nwt", None, "S"): {
        "pubName": "La Biblia. Traducción del Nuevo Mundo (revisión del 2019)",
        "files": {"S": {"EPUB": [
            {"file": {"url": NWT_S_URL, "checksum": _md5(FILE_BODIES[NWT_S_URL])}}
        ]}},
    },
    ("nwt", None, "E"): {
        "pubName": "New World Translation of the Holy Scriptures (2013 Revision)",
        "files": {"E": {"EPUB": [{"file": {"url": "http://files.example/nwt_E.epub"}}]}},
    },
    ("sjjm", None, "S"): {
        "pubName": "Cantemos con alegría",
        "files": {"S": {"MP4": [
            {"track": 0, "title": "Descargar todo (ZIP)", "label": "720p",
             "file": {"url": "http://files.example/sjjm_S_zip.mp4"}},
            {"track": 1, "title": "1. Las cualidades principales de Jehová", "label": "720p",
             "file": {"url": SJJM_S_URL, "checksum": _md5(FILE_BODIES[SJJM_S_URL])}},
            {"track": 1, "title": "1. Las cualidades principales de Jehová", "label": "480p",
             "file": {"url": "http://files.example/sjjm_S_1_480p.mp4"}},
        ]}},
    },
    ("sjjm", None, "E"): {
        "pubName": "Sing Out Joyfully",
        "files": {"E": {"MP4": [
            {"track": 1, "title": "1. Jehovah&#39;s Attributes", "label": "720p",
             "file": {"url": "http://files.example/sjjm_E_1_720p.mp4"}},
        ]}},
    },
    (502014331, None, "S"): {
        "pubName": "Video por ID de documento",
        "files": {"S": {"MP4": [
            {"track": 1, "title": "Episodio 1", "label": "720p",
             "file": {"url": DOCID_S_URL, "checksum": _md5(FILE_BODIES[DOCID_S_URL])}},
        ]}},
    },
    ("g", "202011", "S"): {
        "pubName": "¡Despertad!",
        "formattedDate": "No. 3 2020",
        "files": {"S": {"EPUB": [
            {"file": {"url": G_202011_S_URL, "checksum": _md5(FILE_BODIES[G_202011_S_URL])}}
        ]}},
    },
    ("g", "202011", "E"): {
        "pubName": "Awake!",
        "formattedDate": "No. 3 2020",
        "files": {"E": {"EPUB": [{"file": {"url": "http://files.example/g_202011_E.epub"}}]}},
    },
}


class FakeHTTP:
    """Stand-in for requests.Response supporting both api and download usage."""

    def __init__(self, *, json_data=None, body=b"", status=200):
        self._json = json_data
        self._body = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} Client Error")
            err.response = self
            raise err

    def json(self):
        return self._json

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_get(url, params=None, timeout=None, stream=False, **kwargs):
    if url == api.LANGUAGES_URL:
        return FakeHTTP(json_data=_LANGUAGES)
    if url == api.PUBMEDIA_URL:
        identifier = params.get("docid") or params.get("pub")
        key = (identifier, params.get("issue"), params["langwritten"])
        if key not in _PUBMEDIA:
            return FakeHTTP(status=404)
        return FakeHTTP(json_data=_PUBMEDIA[key])
    # Otherwise it's a file download.
    if url in FILE_BODIES:
        return FakeHTTP(body=FILE_BODIES[url])
    return FakeHTTP(status=404)


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Run inside a temp dir with valid config files and mocked HTTP.

    Returns the output directory the CLI should write into.
    """
    (tmp_path / "products.yaml").write_text(
        "languages: [S]\n"
        "default:\n  formats: [EPUB]\n"
        "products: [nwt]\n"
    )
    (tmp_path / "videos.yaml").write_text(
        "languages: [S]\n"
        "defaults:\n  resolution: 720p\n  formats: [mp4]\n"
        "videos: ['sjjm:1']\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests, "get", _fake_get)
    return tmp_path / "out"


def _run(argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["harbor-fetch", *argv])
    main()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_cli_downloads_with_vernacular_names(cli_env, monkeypatch, capsys):
    _run(["-o", str(cli_env)], monkeypatch)

    lang_dir = cli_env / "S-Spanish"
    pub = lang_dir / "nwt-S-La Biblia. Traducción del Nuevo Mundo (revisión del 2019).epub"
    vid = lang_dir / "sjjm-S-720p-1. Las cualidades principales de Jehová.mp4"

    assert pub.read_bytes() == FILE_BODIES[NWT_S_URL]
    assert vid.read_bytes() == FILE_BODIES[SJJM_S_URL]
    # The 480p variant and the track-0 ZIP must not have been written.
    assert sorted(p.name for p in lang_dir.iterdir()) == [pub.name, vid.name]

    out = capsys.readouterr().out
    assert "2 downloaded" in out


def test_cli_english_titles_renames_but_keeps_vernacular_content(cli_env, monkeypatch):
    _run(["-o", str(cli_env), "--english-titles"], monkeypatch)

    lang_dir = cli_env / "S-Spanish"
    pub = lang_dir / "nwt-S-New World Translation of the Holy Scriptures (2013 Revision).epub"
    vid = lang_dir / "sjjm-S-720p-1. Jehovah's Attributes.mp4"

    # English title in the name, but the bytes are still the Spanish edition.
    assert pub.read_bytes() == FILE_BODIES[NWT_S_URL]
    assert vid.read_bytes() == FILE_BODIES[SJJM_S_URL]
    # No vernacular-named files should exist alongside.
    assert not (lang_dir / "nwt-S-La Biblia. Traducción del Nuevo Mundo (revisión del 2019).epub").exists()


def test_cli_skips_unchanged_files_on_rerun(cli_env, monkeypatch, capsys):
    _run(["-o", str(cli_env)], monkeypatch)
    capsys.readouterr()  # discard first-run output

    _run(["-o", str(cli_env)], monkeypatch)
    out = capsys.readouterr().out

    assert "already up to date" in out
    assert "0 downloaded, 2 already up to date" in out


def test_cli_dry_run_writes_nothing(cli_env, monkeypatch, capsys):
    _run(["-o", str(cli_env), "--dry-run"], monkeypatch)

    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "Dry run complete" in out
    assert not cli_env.exists()  # nothing written to the output directory


def test_cli_periodical_download(tmp_path, monkeypatch, capsys):
    """A symbol-dash-issue entry downloads via the issue API param, and the
    issue date appears in the filename. --english-titles works for periodicals."""
    (tmp_path / "products.yaml").write_text(
        "languages: [S]\n"
        "default:\n  formats: [EPUB]\n"
        "products: ['g-202011']\n"
    )
    (tmp_path / "videos.yaml").write_text("languages: []\nvideos: []\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests, "get", _fake_get)
    out_dir = tmp_path / "out"

    monkeypatch.setattr(sys, "argv", ["harbor-fetch", "--only-products", "-o", str(out_dir)])
    main()

    lang_dir = out_dir / "S-Spanish"
    expected = lang_dir / "g-202011-S-¡Despertad! No. 3 2020.epub"
    assert expected.read_bytes() == FILE_BODIES[G_202011_S_URL]
    assert "1 downloaded" in capsys.readouterr().out


def test_cli_periodical_english_titles(tmp_path, monkeypatch):
    """--english-titles resolves the English issue title for periodicals."""
    (tmp_path / "products.yaml").write_text(
        "languages: [S]\n"
        "default:\n  formats: [EPUB]\n"
        "products: ['g-202011']\n"
    )
    (tmp_path / "videos.yaml").write_text("languages: []\nvideos: []\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests, "get", _fake_get)
    out_dir = tmp_path / "out"

    monkeypatch.setattr(sys, "argv", ["harbor-fetch", "--only-products", "--english-titles", "-o", str(out_dir)])
    main()

    lang_dir = out_dir / "S-Spanish"
    assert (lang_dir / "g-202011-S-Awake! No. 3 2020.epub").exists()
    assert not (lang_dir / "g-202011-S-¡Despertad! No. 3 2020.epub").exists()


def test_cli_docid_video_download(tmp_path, monkeypatch, capsys):
    """A numeric docid entry in videos.yaml downloads via the docid API param,
    with track filtering and language iteration working identically to a symbol."""
    (tmp_path / "products.yaml").write_text(
        "languages: [S]\ndefault:\n  formats: [EPUB]\nproducts: []\n"
    )
    (tmp_path / "videos.yaml").write_text(
        "languages: [S]\n"
        "defaults:\n  resolution: 720p\n  formats: [mp4]\n"
        "videos: ['502014331:1']\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests, "get", _fake_get)
    out_dir = tmp_path / "out"

    monkeypatch.setattr(sys, "argv", ["harbor-fetch", "--only-videos", "-o", str(out_dir)])
    main()

    lang_dir = out_dir / "S-Spanish"
    expected = lang_dir / "502014331-S-720p-Episodio 1.mp4"
    assert expected.read_bytes() == FILE_BODIES[DOCID_S_URL]

    out = capsys.readouterr().out
    assert "1 downloaded" in out
