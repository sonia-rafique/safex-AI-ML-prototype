from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

import pandas as pd
from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
FAQ_JSON_PATH: Final[Path] = PROJECT_ROOT / "data" / "safex_faqs.json"

FALLBACK_MESSAGE: Final[str] = (
    "Thanks for reaching out to SafeX Solutions! I couldn't find an exact "
    "answer to that in our FAQ - let me connect you with a team member who "
    "can help. In the meantime, feel free to ask about our services, "
    "pricing, or how to get started."
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("safex.app")


class FAQItem(BaseModel):
    id: str
    category: str
    question: str
    answer: str
    keywords: list[str]


class FAQListResponse(BaseModel):
    count: int
    results: list[FAQItem]


_faq_df: pd.DataFrame = pd.DataFrame()


def load_faq_dataframe(path: Path = FAQ_JSON_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"FAQ dataset not found at {path}. "
            "Run `python -m src.data_processor` first to generate it."
        )

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    faqs = payload.get("faqs", [])
    if not faqs:
        raise ValueError(f"No FAQ records found in {path}.")

    df = pd.DataFrame.from_records(faqs)
    logger.info("Loaded %d FAQ records from %s", len(df), path)
    return df


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _faq_df
    _faq_df = load_faq_dataframe()
    yield


app = FastAPI(
    title="SafeX Solutions FAQ Knowledge Base API",
    description=(
        "Serves structured FAQ data about SafeX Solutions' services, pricing, "
        "company background, and contact info for the WhatsApp Auto-Reply Bot."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def find_best_matches(query: str, top_n: int = 5) -> pd.DataFrame:
    normalized_query = query.strip().lower()
    normalized_query = "".join([c for c in normalized_query if c.isalnum() or c.isspace()])
    query_terms = [term for term in normalized_query.split() if term]

    if not query_terms or _faq_df.empty:
        return _faq_df.iloc[0:0]

    stop_words = {
        "do", "you", "provide", "what", "is", "does", "the", "a", "an", "for", 
        "how", "can", "i", "with", "my", "your", "of", "in", "at", "on", "me", 
        "fix", "broken", "office", "laptop", "screen", "repair"
    }

    def relevance_score(row: pd.Series) -> int:
        score = 0
        
        q_text = " ".join([w for w in str(row["question"]).lower().split() if w.isalnum()])
        a_text = " ".join([w for w in str(row["answer"]).lower().split() if w.isalnum()])
        k_text = " ".join(row["keywords"]).lower()
        
        for term in query_terms:
            if term in stop_words:
                continue
                
            if term in k_text.split():
                score += 25
            if term in q_text.split():
                score += 15
            if term in a_text.split():
                score += 5
                
        return score

    scored = _faq_df.copy()
    scored["_score"] = scored.apply(relevance_score, axis=1)
    
    matches = scored.loc[scored["_score"] >= 20].sort_values("_score", ascending=False)
    return matches.head(top_n).drop(columns="_score")

@app.get("/", tags=["Health"])
def read_root() -> dict:
    return {
        "status": "ok",
        "message": "SafeX Solutions FAQ Knowledge Base API is running.",
        "total_faqs": len(_faq_df),
        "docs": "/docs",
    }


@app.get("/faqs", response_model=FAQListResponse, tags=["FAQs"])
def get_all_faqs() -> FAQListResponse:
    results = _faq_df.to_dict(orient="records")
    return FAQListResponse(count=len(results), results=results)


@app.get("/faqs/category/{category_name}", response_model=FAQListResponse, tags=["FAQs"])
def get_faqs_by_category(category_name: str) -> FAQListResponse:
    mask = _faq_df["category"].str.lower() == category_name.strip().lower()
    matches = _faq_df.loc[mask]

    if matches.empty:
        available = sorted(_faq_df["category"].unique().tolist())
        raise HTTPException(
            status_code=404,
            detail=(
                f"No FAQs found for category '{category_name}'. "
                f"Available categories: {available}"
            ),
        )

    results = matches.to_dict(orient="records")
    return FAQListResponse(count=len(results), results=results)


@app.get("/faqs/search", response_model=FAQListResponse, tags=["FAQs"])
def search_faqs(
    query: str = Query(..., min_length=1, description="Keyword or phrase to search for")
) -> FAQListResponse:
    matches = find_best_matches(query, top_n=len(_faq_df))

    if matches.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No FAQs matched the query '{query}'. Try a different keyword.",
        )

    results = matches.to_dict(orient="records")
    return FAQListResponse(count=len(results), results=results)


@app.post("/webhook/whatsapp", tags=["WhatsApp"])
def whatsapp_webhook(Body: str = Form(...), From: str = Form(default="")) -> Response:
    incoming_message = Body.strip()
    logger.info("WhatsApp message from %s: %r", From or "unknown", incoming_message)

    if incoming_message:
        matches = find_best_matches(incoming_message, top_n=1)
    else:
        matches = _faq_df.iloc[0:0]

    if matches.empty:
        reply_text = FALLBACK_MESSAGE
        logger.info("No FAQ match for %r - sending fallback message.", incoming_message)
    else:
        reply_text = matches.iloc[0]["answer"]
        logger.info("Matched FAQ id=%s for %r", matches.iloc[0]["id"], incoming_message)

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{_escape_xml(reply_text)}</Message></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)