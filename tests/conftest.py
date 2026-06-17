"""Shared fixtures and helpers for the harbor_fetch test suite."""

import pytest
import requests

from harbor_fetch import api


class FakeResponse:
    """Minimal stand-in for a requests.Response used to mock network calls."""

    def __init__(self, json_data=None, status_code=200):
        self._json = {} if json_data is None else json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} Client Error")
            err.response = self
            raise err

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear lru_cache state on the English-title lookups before every test.

    These helpers are cached per arguments for the lifetime of a process, so
    without this the result of one test would leak into the next.
    """
    api.fetch_pub_english_name.cache_clear()
    api.fetch_video_english_titles.cache_clear()
    yield
    api.fetch_pub_english_name.cache_clear()
    api.fetch_video_english_titles.cache_clear()
