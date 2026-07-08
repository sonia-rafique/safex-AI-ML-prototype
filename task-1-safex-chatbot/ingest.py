"""
ingest.py
---------
Advanced ingestion pipeline for the SafeX Solutions Agentic RAG system.

What this does (upgraded vs. the original version):
1. Crawls the SafeX Solutions website starting from the homepage and follows
   internal links up to a configurable depth (not just the homepage anymore).
2. Cleans each page and keeps track of WHICH url each chunk came from
   (metadata), so the agent can eventually cite sources.
3. Uses the correct, current Gemini embedding model name.
4. Splits with overlap-aware chunking tuned for FAQ-style short passages.
5. Persists everything into a local Chroma vector store.

Run with:
    python ingest.py
"""

import os
import time
import logging
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("ingest")

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
BASE_URL = "https://safexsolutions.com/"
ALLOWED_DOMAIN = urlparse(BASE_URL).netloc
MAX_PAGES = 25          # safety cap so a crawl can't run away
REQUEST_TIMEOUT = 20
CRAWL_DELAY_SECONDS = 0.5   # be polite to the target server
PERSIST_DIR = "./safex_db"
EMBEDDING_MODEL = "models/gemini-embedding-001"  # current stable Gemini embedding model

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _clean_soup(soup: BeautifulSoup) -> str:
    """Strip non-content tags and return readable text."""
    for tag in soup(["script", "style", "header", "footer", "nav", "noscript", "svg", "form"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _extract_links(soup: BeautifulSoup, current_url: str) -> list[str]:
    """Return same-domain links found on the page."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full_url = urljoin(current_url, href)
        parsed = urlparse(full_url)
        # normalize: drop fragments/query noise, keep only the target domain
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.netloc == ALLOWED_DOMAIN:
            links.append(clean_url.rstrip("/"))
    return links


def crawl_site(base_url: str = BASE_URL, max_pages: int = MAX_PAGES) -> list[Document]:
    """
    Breadth-first crawl of the SafeX site, starting at base_url.
    Returns a list of langchain Documents, one per page, each carrying
    the source URL in its metadata.
    """
    log.info("Starting crawl at %s (max_pages=%s)", base_url, max_pages)

    visited: set[str] = set()
    queue: deque[str] = deque([base_url.rstrip("/")])
    documents: list[Document] = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("Skipping %s (request failed: %s)", url, e)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        links = _extract_links(soup, url)
        text = _clean_soup(soup)

        if len(text) >= 200:
            documents.append(
                Document(
                    page_content=text,
                    metadata={"source": url},
                )
            )
            log.info("Scraped %s (%d chars)", url, len(text))
        else:
            log.info("Skipped %s (too little content: %d chars)", url, len(text))

        for link in links:
            if link not in visited and link not in queue:
                queue.append(link)

        time.sleep(CRAWL_DELAY_SECONDS)

    log.info("Crawl finished. %d pages collected.", len(documents))
    return documents


def chunk_documents(documents: list[Document]) -> list[Document]:
    """Split page-level documents into retrieval-friendly chunks."""
    log.info("Splitting %d page(s) into chunks...", len(documents))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(documents)
    log.info("Created %d chunks.", len(chunks))
    return chunks


def build_vector_database(chunks: list[Document]) -> None:
    """Embed chunks with Gemini and persist them into a Chroma collection."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Add it to your .env file.")

    log.info("Generating embeddings with model=%s ...", EMBEDDING_MODEL)
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )

    log.info("Writing to Chroma at %s ...", PERSIST_DIR)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
        collection_name="safex_faq",
    )
    log.info("Vector database created successfully at %s", PERSIST_DIR)


def main() -> None:
    pages = crawl_site()
    if not pages:
        log.error("No content scraped. Aborting ingestion.")
        return

    chunks = chunk_documents(pages)
    build_vector_database(chunks)


if __name__ == "__main__":
    main()