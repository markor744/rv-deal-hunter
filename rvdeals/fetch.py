"""Polite page fetching: normal browser User-Agent, a pause between requests, and a
robots.txt check every run (if a site starts blocking us, we stop and report it)."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class BlockedByRobots(Exception):
    pass


class Fetcher:
    def __init__(self, pause_seconds: float = 3.0, timeout: float = 30.0):
        self.pause = pause_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT,
                                     "Accept-Language": "en-CA,en;q=0.9"})
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last = 0.0
        self.requests_made = 0

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(host)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._get(host + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[host] = rp
        return rp.can_fetch("*", url)

    def _get(self, url: str) -> requests.Response:
        wait = self.pause - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.session.get(url, timeout=self.timeout)
        finally:
            self._last = time.monotonic()
            self.requests_made += 1

    def get(self, url: str) -> str:
        if not self._allowed(url):
            raise BlockedByRobots(url)
        r = self._get(url)
        r.raise_for_status()
        return r.text
