"""Tests for harbor_fetch.api — focused on the English-title lookups added for
the --english-titles feature, plus the VideoItem.track field they depend on."""

from unittest.mock import patch

import requests

from harbor_fetch import api
from harbor_fetch.api import (
    fetch_pub_english_name,
    fetch_pub_links,
    fetch_video_english_titles,
    fetch_video_links,
)

from .conftest import FakeResponse


# ── fetch_pub_english_name ────────────────────────────────────────────────────

def test_pub_english_name_returns_unescaped_title():
    resp = FakeResponse({"pubName": "Enjoy Life Forever! &amp; Beyond"})
    with patch.object(api.requests, "get", return_value=resp):
        assert fetch_pub_english_name("lff", "EPUB") == "Enjoy Life Forever! & Beyond"


def test_pub_english_name_queries_english_with_given_formats():
    resp = FakeResponse({"pubName": "Some Title"})
    with patch.object(api.requests, "get", return_value=resp) as mock_get:
        fetch_pub_english_name("nwt", "EPUB,PDF,JWPUB")
    params = mock_get.call_args.kwargs["params"]
    assert params["langwritten"] == "E"
    assert params["fileformat"] == "EPUB,PDF,JWPUB"
    assert params["pub"] == "nwt"


def test_pub_english_name_returns_none_on_404():
    resp = FakeResponse(status_code=404)
    with patch.object(api.requests, "get", return_value=resp):
        assert fetch_pub_english_name("nopub", "EPUB") is None


def test_pub_english_name_returns_none_on_400():
    # Mixing incompatible formats makes the real API return 400 for some pubs.
    resp = FakeResponse(status_code=400)
    with patch.object(api.requests, "get", return_value=resp):
        assert fetch_pub_english_name("nwt", "EPUB,MP4") is None


def test_pub_english_name_returns_none_on_connection_error():
    with patch.object(api.requests, "get", side_effect=requests.ConnectionError("boom")):
        assert fetch_pub_english_name("lff", "EPUB") is None


def test_pub_english_name_is_cached_per_symbol_and_formats():
    resp = FakeResponse({"pubName": "Cached Title"})
    with patch.object(api.requests, "get", return_value=resp) as mock_get:
        fetch_pub_english_name("lff", "EPUB")
        fetch_pub_english_name("lff", "EPUB")          # same args -> cache hit
        fetch_pub_english_name("lff", "PDF")           # different formats -> miss
    assert mock_get.call_count == 2


# ── fetch_video_english_titles ────────────────────────────────────────────────

def _video_payload(lang="E"):
    return {
        "files": {
            lang: {
                "MP4": [
                    {"track": 0, "title": "Download All (ZIP)", "label": "720p"},
                    {"track": 1, "title": "Jehovah&#39;s Attributes", "label": "720p"},
                    {"track": 1, "title": "Jehovah&#39;s Attributes", "label": "480p"},
                    {"track": 2, "title": "Jehovah Is Your Name", "label": "720p"},
                ]
            }
        }
    }


def test_video_english_titles_maps_track_to_title_and_skips_zip():
    resp = FakeResponse(_video_payload())
    with patch.object(api.requests, "get", return_value=resp):
        titles = fetch_video_english_titles("sjjm", "MP4")
    assert titles == {1: "Jehovah's Attributes", 2: "Jehovah Is Your Name"}
    assert 0 not in titles  # track 0 (ZIP bundle) excluded


def test_video_english_titles_dedupes_across_resolutions():
    resp = FakeResponse(_video_payload())
    with patch.object(api.requests, "get", return_value=resp):
        titles = fetch_video_english_titles("sjjm", "MP4")
    # Track 1 appears at both 720p and 480p but yields a single entry.
    assert titles[1] == "Jehovah's Attributes"


def test_video_english_titles_falls_back_to_first_language_block():
    # If the response isn't keyed by "E", the first language block is used.
    resp = FakeResponse(_video_payload(lang="X"))
    with patch.object(api.requests, "get", return_value=resp):
        titles = fetch_video_english_titles("sjjm", "MP4")
    assert titles == {1: "Jehovah's Attributes", 2: "Jehovah Is Your Name"}


def test_video_english_titles_returns_empty_on_404():
    resp = FakeResponse(status_code=404)
    with patch.object(api.requests, "get", return_value=resp):
        assert fetch_video_english_titles("nopub", "MP4") == {}


def test_video_english_titles_returns_empty_on_error():
    with patch.object(api.requests, "get", side_effect=requests.Timeout("slow")):
        assert fetch_video_english_titles("sjjm", "MP4") == {}


# ── fetch_video_links — the track field that title-matching relies on ─────────

def test_fetch_video_links_populates_track_and_filters():
    payload = {
        "files": {
            "S": {
                "MP4": [
                    {"track": 0, "title": "ZIP", "label": "720p",
                     "file": {"url": "http://x/zip.mp4"}},
                    {"track": 1, "title": "Uno", "label": "720p",
                     "file": {"url": "http://x/1-720.mp4", "checksum": "abc"}},
                    {"track": 1, "title": "Uno", "label": "480p",
                     "file": {"url": "http://x/1-480.mp4"}},
                    {"track": 2, "title": "Dos", "label": "720p",
                     "file": {"url": "http://x/2-720.mp4"}},
                ]
            }
        }
    }
    resp = FakeResponse(payload)
    with patch.object(api.requests, "get", return_value=resp):
        items = fetch_video_links("sjjm", "S", resolution="720p", formats="MP4")

    # track 0 skipped; only 720p kept -> tracks 1 and 2
    assert [i.track for i in items] == [1, 2]
    assert items[0].track == 1
    assert items[0].resolution == "720p"
    assert items[0].checksum == "abc"
    assert items[1].track == 2


def test_fetch_video_links_respects_track_filter():
    payload = {
        "files": {
            "S": {
                "MP4": [
                    {"track": 1, "title": "Uno", "label": "720p",
                     "file": {"url": "http://x/1.mp4"}},
                    {"track": 2, "title": "Dos", "label": "720p",
                     "file": {"url": "http://x/2.mp4"}},
                    {"track": 3, "title": "Tres", "label": "720p",
                     "file": {"url": "http://x/3.mp4"}},
                ]
            }
        }
    }
    resp = FakeResponse(payload)
    with patch.object(api.requests, "get", return_value=resp):
        items = fetch_video_links("sjjm", "S", resolution="720p",
                                  formats="MP4", tracks=[1, 3])
    assert [i.track for i in items] == [1, 3]


# ── fetch_pub_links — vernacular title source ─────────────────────────────────

def test_fetch_pub_links_uses_vernacular_pubname():
    payload = {
        "pubName": "La Biblia &amp; m\u00e1s",
        "files": {
            "S": {
                "EPUB": [{"file": {"url": "http://x/nwt_S.epub", "checksum": "d1"}}],
            }
        },
    }
    resp = FakeResponse(payload)
    with patch.object(api.requests, "get", return_value=resp):
        items = fetch_pub_links("nwt", "S", formats="EPUB")
    assert len(items) == 1
    assert items[0].pub_name == "La Biblia & más"
    assert items[0].format == "EPUB"
    assert items[0].lang_code == "S"
    assert items[0].checksum == "d1"
