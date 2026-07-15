from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Final

import pandas as pd

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
RAW_TEXT_PATH: Final[Path] = PROJECT_ROOT / "data" / "raw_scraped_text.txt"
OUTPUT_JSON_PATH: Final[Path] = PROJECT_ROOT / "data" / "safex_faqs.json"

LLM_MAX_INPUT_CHARS: Final[int] = 40_000
LLM_MAX_NEW_FAQS: Final[int] = 50

_LLM_SYSTEM_PROMPT = """You are a meticulous data engineer. Extract at least 40 to 50 detailed FAQ-style question/answer pairs from the provided text for SafeX Solutions.

Break down every small detail, specific service, sub-capability (like vulnerability monitoring, e-commerce features, contact emails, specific locations, tech stacks mentioned, training, etc.) into its own explicit, granular Q&A pair.

Rules:
- Capture every minute detail. Do not summarize or bundle services. Create separate FAQs for specific sub-services.
- Each answer must be precise, professional, and a complete standalone sentence or two.
- Categorize each: Services, Pricing, Company, Contact, Process, Social Impact.
- Return ONLY a raw JSON array of objects. No markdown formatting, no code blocks, no preamble. 
Each item must strictly look like: {"category": "...", "question": "...", "answer": "...", "keywords": ["...", "..."]}"""


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("safex.data_processor")


def load_raw_text(path: Path = RAW_TEXT_PATH) -> str:
    if not path.exists():
        logger.warning(
            "Raw scraped text not found at %s. "
            "Run `python -m src.scraper` first if you want live site text. "
            "Continuing with the curated FAQ dataset only.",
            path,
        )
        return ""

    text = path.read_text(encoding="utf-8")
    preview = text[:200].replace("\n", " ")
    logger.info("Loaded %d characters of raw scraped text. Preview: %s...", len(text), preview)
    return text


def build_faq_records() -> list[dict]:
    records: list[dict] = [
        {
            "id": "svc-001",
            "category": "Services",
            "question": "What services does SafeX Solutions offer?",
            "answer": (
                "SafeX Solutions offers a full suite of digital services, including "
                "Cybersecurity (data security, network protection, vulnerability "
                "assessments, and threat monitoring), Web Development (responsive, "
                "SEO-friendly websites and e-commerce platforms), Mobile App "
                "Development, Creative UI/UX Design and Branding, SEO, Digital "
                "Marketing, and IT Consulting."
            ),
            "keywords": ["services", "offer", "what do you do", "capabilities"],
        },
        {
            "id": "svc-002",
            "category": "Services",
            "question": "Does SafeX Solutions provide cybersecurity services?",
            "answer": (
                "Yes. Cybersecurity is one of SafeX Solutions' core specialties, "
                "covering data security, network protection, vulnerability "
                "assessments, and continuous threat monitoring for businesses "
                "of all sizes."
            ),
            "keywords": ["cybersecurity", "security", "vulnerability", "threat", "protection"],
        },
        {
            "id": "svc-003",
            "category": "Services",
            "question": "Can SafeX Solutions build a website or web application for my business?",
            "answer": (
                "Yes. The Web Development team builds responsive, SEO-friendly "
                "websites, custom web applications, and secure e-commerce "
                "platforms tailored to your business requirements."
            ),
            "keywords": ["website", "web development", "web app", "ecommerce"],
        },
        {
            "id": "svc-004",
            "category": "Services",
            "question": "Does SafeX Solutions do mobile app development?",
            "answer": (
                "Yes, SafeX Solutions builds custom mobile applications as part "
                "of its digital services portfolio, alongside web and desktop "
                "solutions."
            ),
            "keywords": ["mobile app", "app development", "ios", "android"],
        },
        {
            "id": "svc-005",
            "category": "Services",
            "question": "What creative or design services are available?",
            "answer": (
                "SafeX Solutions offers Creative UI/UX Design, branding, graphic "
                "design, and logo creation to help businesses build a strong and "
                "memorable digital identity."
            ),
            "keywords": ["design", "ui/ux", "branding", "logo", "graphic design"],
        },
        {
            "id": "svc-006",
            "category": "Services",
            "question": "Does SafeX Solutions offer SEO and marketing services?",
            "answer": (
                "Yes. SafeX Solutions provides SEO and data-driven digital "
                "marketing services designed to increase a brand's visibility, "
                "engagement, and conversions."
            ),
            "keywords": ["seo", "marketing", "search engine optimization", "visibility"],
        },
        {
            "id": "price-001",
            "category": "Pricing",
            "question": "What is the minimum project budget for working with SafeX Solutions?",
            "answer": (
                "Most engagements with SafeX Solutions start at a minimum "
                "project budget of $1,000+, depending on scope and complexity."
            ),
            "keywords": ["minimum budget", "project cost", "price", "how much"],
        },
        {
            "id": "price-002",
            "category": "Pricing",
            "question": "What are SafeX Solutions' hourly rates?",
            "answer": (
                "SafeX Solutions' hourly rates typically range from $25 to $49 "
                "per hour, depending on the service and the expertise required."
            ),
            "keywords": ["hourly rate", "cost per hour", "pricing", "rate"],
        },
        {
            "id": "company-001",
            "category": "Company",
            "question": "Where is SafeX Solutions based?",
            "answer": (
                "SafeX Solutions is headquartered in Islamabad, Pakistan, and "
                "serves clients internationally across more than a dozen "
                "countries."
            ),
            "keywords": ["location", "based", "headquarters", "islamabad", "pakistan"],
        },
        {
            "id": "company-002",
            "category": "Company",
            "question": "How many clients has SafeX Solutions worked with?",
            "answer": (
                "SafeX Solutions has served 80+ international clients, "
                "delivering cybersecurity, development, design, and marketing "
                "projects across a wide range of industries."
            ),
            "keywords": ["clients", "customers", "experience", "portfolio"],
        },
        {
            "id": "company-003",
            "category": "Company",
            "question": "What kind of company is SafeX Solutions?",
            "answer": (
                "SafeX Solutions is a global digital services and cybersecurity "
                "company focused on helping businesses innovate, grow, and stay "
                "protected through secure, technology-driven solutions."
            ),
            "keywords": ["about", "company", "who are you", "overview"],
        },
        {
            "id": "contact-001",
            "category": "Contact",
            "question": "How do I get started with a project?",
            "answer": (
                "You can get started by reaching out through the SafeX "
                "Solutions website (safexsolutions.com) or this WhatsApp chat "
                "to share your project needs, budget, and timeline. A team "
                "member will follow up to scope the work with you."
            ),
            "keywords": ["get started", "start a project", "how to begin", "onboarding"],
        },
        {
            "id": "contact-002",
            "category": "Contact",
            "question": "How can I contact SafeX Solutions?",
            "answer": (
                "You can contact SafeX Solutions via this WhatsApp chat, through "
                "the contact form on safexsolutions.com, or by sending a direct "
                "message describing your project needs."
            ),
            "keywords": ["contact", "reach", "email", "phone", "whatsapp"],
        },
    ]
    logger.info("Built %d curated FAQ records", len(records))
    return records


def extract_faqs_with_llm(
    raw_text: str,
    model: str = "gemini-flash-latest",
    max_new_faqs: int = LLM_MAX_NEW_FAQS,
) -> list[dict]:
    if not raw_text.strip():
        logger.info("Skipping LLM extraction: no raw scraped text available.")
        return []

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.info(
            "Skipping LLM extraction: GEMINI_API_KEY is not set. "
            "Set it to auto-extract more FAQs from scraped text for free!"
        )
        return []

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning(
            "Skipping LLM extraction: 'google-genai' package is not installed. "
            "Run `pip install google-genai` to enable this step."
        )
        return []

    truncated_text = raw_text[:LLM_MAX_INPUT_CHARS]
    
    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model=model,
            contents=f"Extract up to {max_new_faqs} FAQ pairs from this scraped website text:\n\n{truncated_text}",
            config=types.GenerateContentConfig(
                system_instruction=_LLM_SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        raw_response_text = response.text.strip()
    except Exception as exc:
        logger.warning("Gemini extraction call failed, skipping: %s", exc)
        return []

    raw_response_text = re.sub(r"^```(json)?|```$", "", raw_response_text, flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(raw_response_text)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse Gemini extraction output as JSON: %s", exc)
        return []

    if not isinstance(parsed, list):
        logger.warning("Gemini extraction output was not a JSON array.")
        return []

    records: list[dict] = []
    for i, item in enumerate(parsed[:max_new_faqs]):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        category = str(item.get("category", "")).strip() or "Company"
        keywords = item.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []

        if not question or not answer:
            continue

        records.append(
            {
                "id": f"gemini-{i + 1:03d}",
                "category": category,
                "question": question,
                "answer": answer,
                "keywords": [str(k).strip().lower() for k in keywords if str(k).strip()],
            }
        )

    logger.info("Gemini extraction produced %d usable FAQ record(s) from scraped website", len(records))
    return records


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)

    text_columns = ["id", "category", "question", "answer"]
    for col in text_columns:
        df[col] = df[col].astype(str).str.strip()

    df["category"] = df["category"].str.title()

    df["keywords"] = df["keywords"].apply(
        lambda kws: sorted({str(k).strip().lower() for k in kws})
    )

    if df["id"].duplicated().any():
        df["id"] = [f"faq-{i + 1:03d}" for i in range(len(df))]
        logger.warning("Duplicate ids detected after merge; re-assigned sequential ids.")

    if (df["question"] == "").any() or (df["answer"] == "").any():
        raise ValueError("Found FAQ records with an empty question or answer.")

    logger.info(
        "DataFrame ready: %d rows across categories: %s",
        len(df),
        ", ".join(sorted(df["category"].unique())),
    )
    return df


def save_faqs_json(df: pd.DataFrame, output_path: Path = OUTPUT_JSON_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = df.to_dict(orient="records")
    payload = {
        "meta": {
            "source": "SafeX Solutions (https://safexsolutions.com)",
            "generated_by": "src/data_processor.py",
            "total_faqs": len(records),
            "categories": sorted(df["category"].unique().tolist()),
        },
        "faqs": records,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("Wrote %d FAQ records to %s", len(records), output_path)


def run() -> Path:
    raw_text = load_raw_text()
    
    curated_records = build_faq_records()
    
    gemini_records = extract_faqs_with_llm(raw_text)
    
    all_records = curated_records + gemini_records
    
    df = to_dataframe(all_records)
    save_faqs_json(df)
    return OUTPUT_JSON_PATH


if __name__ == "__main__":
    run()