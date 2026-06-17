"""Tests for filename construction in harbor_fetch.__main__.

These cover the English-vs-vernacular title selection introduced by
--english-titles, and the filesystem-unsafe character sanitizing applied to
every saved file name.
"""

from harbor_fetch.api import DownloadItem, VideoItem
from harbor_fetch.__main__ import _safe, pub_filename, video_filename


def _pub(pub_name="Vernáculo", fmt="EPUB"):
    return DownloadItem(
        pub_symbol="lff", lang_code="S", pub_name=pub_name,
        format=fmt, url="http://x/lff_S.epub", checksum=None,
    )


def _video(title="Título", track=1):
    return VideoItem(
        symbol="sjjm", lang_code="S", track=track, title=title,
        resolution="720p", format="MP4", url="http://x/v.mp4", checksum=None,
    )


# ── _safe ─────────────────────────────────────────────────────────────────────

def test_safe_replaces_each_unsafe_character():
    assert _safe(r'a\b/c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_safe_leaves_normal_text_untouched():
    assert _safe("Enjoy Life Forever! (2024)") == "Enjoy Life Forever! (2024)"


# ── pub_filename ──────────────────────────────────────────────────────────────

def test_pub_filename_defaults_to_vernacular():
    assert pub_filename(_pub("La Biblia")) == "lff-S-La Biblia.epub"


def test_pub_filename_uses_english_title_when_provided():
    result = pub_filename(_pub("La Biblia"), "New World Translation")
    assert result == "lff-S-New World Translation.epub"


def test_pub_filename_falls_back_when_english_title_is_none():
    assert pub_filename(_pub("La Biblia"), None) == "lff-S-La Biblia.epub"


def test_pub_filename_sanitizes_unsafe_characters_in_title():
    # A colon in the title must not become a path separator on disk.
    result = pub_filename(_pub("Topic: A/B"))
    assert result == "lff-S-Topic_ A_B.epub"


def test_pub_filename_lowercases_extension():
    assert pub_filename(_pub("X", fmt="PDF")).endswith(".pdf")


# ── video_filename ────────────────────────────────────────────────────────────

def test_video_filename_defaults_to_vernacular():
    assert video_filename(_video("Las cualidades")) == "sjjm-S-720p-Las cualidades.mp4"


def test_video_filename_uses_english_title_when_provided():
    result = video_filename(_video("Las cualidades"), "Jehovah's Attributes")
    assert result == "sjjm-S-720p-Jehovah's Attributes.mp4"


def test_video_filename_falls_back_when_english_title_is_none():
    # Mirrors a track present in the vernacular but absent from the English map.
    assert video_filename(_video("Dos", track=2), None) == "sjjm-S-720p-Dos.mp4"
