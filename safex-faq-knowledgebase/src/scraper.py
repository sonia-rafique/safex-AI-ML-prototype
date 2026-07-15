from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Final
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL: Final[str] = "https://safexsolutions.com/"
DOMAIN: Final[str] = urlparse(BASE_URL).netloc

REQUEST_TIMEOUT: Final[int] = 15
CRAWL_DELAY_SECONDS: Final[float] = 1.0
MAX_PAGES: Final[int] = 40

OUTPUT_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "raw_scraped_text.txt"

HEADERS: Final[dict] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

TAGS_TO_STRIP: Final[tuple[str, ...]] = (
    "script", "style", "noscript", "svg", "iframe", "form", "button",
)

SKIP_PATH_FRAGMENTS: Final[tuple[str, ...]] = (
    "/category/", "/tag/", "/project/", "/author/", "/feed",
    "wp-content", "wp-json", "wp-login", ".jpg", ".png", ".pdf", ".zip",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("safex.scraper")


def _build_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_html(url: str, session: requests.Session) -> str | None:
    try:
        logger.info("Fetching URL: %s", url)
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def extract_clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag_name in TAGS_TO_STRIP:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    raw_text = soup.get_text(separator="\n")
    lines = (line.strip() for line in raw_text.splitlines())
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def _should_skip(url: str) -> bool:
    return any(fragment in url for fragment in SKIP_PATH_FRAGMENTS)


def extract_internal_links(html: str, current_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        absolute_url = urljoin(current_url, href)
        parsed = urlparse(absolute_url)

        if parsed.netloc != DOMAIN:
            continue

        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if _should_skip(normalized) or normalized in seen:
            continue

        seen.add(normalized)
        links.append(normalized)

    return links


def crawl(base_url: str = BASE_URL, max_pages: int = MAX_PAGES) -> dict[str, str]:
    session = _build_session()
    visited: set[str] = set()
    queue: list[str] = [base_url]
    pages: dict[str, str] = {}

    try:
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            html = fetch_html(url, session)
            if html is None:
                continue

            clean_text = extract_clean_text(html)
            if clean_text.strip():
                pages[url] = clean_text
                logger.info("Successfully processed page content: %s", url)
            else:
                logger.warning("No extractable plain text from %s", url)

            if len(visited) < max_pages:
                for link in extract_internal_links(html, url):
                    if link not in visited and link not in queue:
                        queue.append(link)

            time.sleep(CRAWL_DELAY_SECONDS)
    finally:
        session.close()

    logger.info("Crawl finished: Visited %d page(s). Total extracted: %d", len(visited), len(pages))
    return pages


def save_pages(pages: dict[str, str], output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    blocks = []
    for url, text in pages.items():
        blocks.append(f"===== PAGE: {url} =====\n{text}")

    output_path.write_text("\n\n".join(blocks), encoding="utf-8")
    logger.info("Saved multi-page deep scraped data chunks to: %s", output_path)


def run(base_url: str = BASE_URL, output_path: Path = OUTPUT_PATH, max_pages: int = MAX_PAGES) -> Path:
    pages = crawl(base_url, max_pages=max_pages)

    if not pages:
        logger.critical("Scrape pipeline failed to pull structure layout from target source.")
        raise RuntimeError("Scrape produced zero layout configuration data blocks.")

    save_pages(pages, output_path)
    return output_path


if __name__ == "__main__":
    try:
        run()
    except RuntimeError:
        sys.exit(1)