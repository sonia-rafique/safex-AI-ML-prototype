# FAQ KNOWLEDGE BASE MODULE

### SafeX Solutions WhatsApp Auto-Reply Bot Core Component

---

### Module Metadata
* **Module Name:** FAQ Knowledge Base API  
* **Developer Name:** Sonia Rafique 
* **Academic Program:** BS Computer Science  
* **Target Enterprise:** SafeX Solutions  
* **Group ID:** Group 24  

---

## Table of Contents
1. [Project Overview and Executive Summary](#1-project-overview-and-executive-summary)
2. [System Architecture and Design](#2-system-architecture-and-design)
3. [Detailed Component Breakdown](#3-detailed-component-breakdown)
4. [Source Code and File Structure](#4-source-code-and-file-structure)
5. [Setup and Execution Instructions](#5-setup-and-execution-instructions)
6. [API Validation and Payload Schemas](#6-api-validation-and-payload-schemas)

---

## 1. Project Overview and Executive Summary

The FAQ Knowledge Base serves as the primary informational core of the SafeX Solutions WhatsApp Auto-Reply Bot. The purpose of this module is to establish an automated data pipeline that bridges unstructured corporate web assets with a structured, query-responsive automated conversational endpoint.

By utilizing dynamic multi-page web crawling, generative semantic extraction, and statistical keyword ranking, this application transforms raw, unstructured web layout content into highly reliable, verified conversational FAQ schemas. The system operates on a dual-source dataset architecture: a set of curated backbone enterprise records combined with live, web-scraped content mined via Google Gemini. To protect the integrity of corporate communications, the system enforces strict token-boundary matching rules and score thresholds to filter out-of-domain requests and serve graceful, contextual fallback responses.

---

## 2. System Architecture and Design

The system is divided into three distinct execution phases, each operating sequentially to fetch, process, and serve conversational data.

### Architectural Workflow

```text
+-----------------------------------------------------------------------------+
|                                  STAGE 1                                    |
|                               [src.scraper]                                 |
| - Initiates Breadth-First Search (BFS) crawler starting from BASE_URL       |
| - Dynamically parses same-domain internal links up to a hard cap of 40 pages|
| - Strips administrative layouts, script elements, and CSS components        |
| - Outputs raw unstructured textual content to data/raw_scraped_text.txt     |
+--------------------------------------+--------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                                  STAGE 2                                    |
|                            [src.data_processor]                             |
| - Loads 13 hand-verified base enterprise structural FAQ records             |
| - Reads raw text assets and validates runtime environment variables         |
| - Leverages google-genai SDK to extract up to 50 explicit FAQ schemas       |
| - Concatenates, de-duplicates, and normalizes datasets using Pandas         |
| - Serializes validated JSON output structure to data/safex_faqs.json        |
+--------------------------------------+--------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                                  STAGE 3                                    |
|                                 [src.app]                                   |
| - Runs high-performance Uvicorn / FastAPI server instance                   |
| - Mounts lifespan context manager to load the FAQ dataset into memory       |
| - Validates exact word-boundary frequencies to rank search queries          |
| - Filters weak semantic inputs below the Confidence Score Threshold of 20    |
| - Responds with valid, escaped TwiML XML to the Twilio Webhook interface   |
+-----------------------------------------------------------------------------+

---

## 3. Detailed Component Breakdown

### A. Web Scraper (`src/scraper.py`)

The scraper operates as a deep web crawler starting from the homepage.

* **State Management:** Uses a First-In-First-Out (FIFO) queue for Breadth-First Search (BFS) link traversal up to 40 pages to ensure complete data coverage.
* **HTTP Adapters:** Uses a custom HTTP session configured with `urllib3.util.retry.Retry` to gracefully handle network fluctuations, rate limits (429), and transient server errors (5xx).
* **Data Cleansing:** Decomposes non-content HTML structures such as `<script>`, `<style>`, and `<noscript>` blocks using BeautifulSoup's `.decompose()` method. It avoids compressing payloads during transmission to prevent character decoding anomalies.

### B. Knowledge Base Processor (`src/data_processor.py`)

The data processor normalizes the raw scraped data and prepares it for query matching.

* **Dual-Data Architecture:** Loads 13 highly authoritative, hand-verified base records ensuring high-reliability service, pricing, and contact replies remain untouched.
* **Generative Knowledge Mining:** Interfaces with the `google-genai` SDK using the `gemini-1.5-flash` model under strict formatting instructions. The model is forced to output schema-conforming JSON objects directly.
* **Pandas Pipeline:** Maps all entities into Pandas DataFrames, enforces sequential index generation, strips leading/trailing spaces, normalizes string casings, and cleans duplicate rows.

### C. FastAPI Conversational Service (`src/app.py`)

The web service serves as the core communication layer.

* **Lifespan Manager:** Loads the compiled JSON records into memory at server startup using FastAPI's lifespan handlers to enable fast, in-memory query processing.
* **Text Ranking Engine:** Filters out conversational noise and standard stop words. It ranks results by matching exact word boundaries across questions, answers, and keywords, assigning weighted scores to noun stems.
* **Confidence Threshold Gate:** Disallows queries that do not score at or above a minimum score of 20, keeping off-topic or irrelevant inquiries from returning false-positive matches.
* **TwiML XML Interface:** Safely escapes special characters (such as `&`, `<`, and `>`) and packages the response in a standardized XML format compatible with Twilio's webhook specifications.

---

## 4. Source Code and File Structure

```text
safex-AI-ML-prototype/
├── task-1-safex-chatbot/
└── task-2-faq-knowledgebase/
    ├── data/
    │   ├── raw_scraped_text.txt         # Raw output from multi-page web scraper
    │   └── safex_faqs.json              # Compiled database containing 58+ clean FAQs
    ├── src/
    │   ├── __init__.py
    │   ├── app.py                       # FastAPI application serving TwiML endpoint
    │   ├── data_processor.py            # Pandas data validation and Gemini pipeline
    │   └── scraper.py                   # Multi-page web crawler
    ├── .gitignore                       # Ensures .venv, .env, and __pycache__ are untracked
    ├── README.md                        # Project technical documentation
    └── requirements.txt                 # Package dependencies

```

---

## 5. Setup and Execution Instructions

### Installation

Activate a clean virtual environment and run the following command to install the required packages:

```bash
pip install -r requirements.txt

```

### Environment Variable Configuration

Configure your Gemini API key inside your terminal instance to enable free-tier content generation:

#### Windows PowerShell

```powershell
$env:GEMINI_API_KEY="your_actual_api_key_here"

```

#### Windows Command Prompt (cmd)

```cmd
set GEMINI_API_KEY=your_actual_api_key_here

```

#### macOS / Linux Terminal

```bash
export GEMINI_API_KEY="your_actual_api_key_here"

```

### Pipeline Execution Commands

Run the pipeline stages in order from your project root directory:

```bash
# Step 1: Execute deep crawling
python -m src.scraper

# Step 2: Compile hardcoded and AI-generated records
python -m src.data_processor

# Step 3: Start the web service
python -m src.app

```

---

## 6. API Validation and Payload Schemas

Once your local server starts, you can verify performance using the following testing protocols:

* **Interactive Swagger Documentation:** Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.
* **Search API Verification:** Test keyword matches directly at [http://127.0.0.1:8000/faqs/search?query=seo](http://127.0.0.1:8000/faqs/search?query=seo).

### Webhook POST Request Specifications

* **Endpoint Path:** `/webhook/whatsapp`
* **Content-Type:** `application/x-www-form-urlencoded`

#### A. Valid Match Sample Input (Form URL-Encoded)

```text
Body=can you tell me how do you guys handle my application development for iOS or mobile phones?
From=+923001234567

```

#### Valid Match Sample Output (TwiML XML)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Yes, SafeX Solutions builds custom mobile applications as part of its digital services portfolio, alongside web and desktop solutions.</Message>
</Response>

```

#### B. Out-Of-Domain Fallback Sample Input (Form URL-Encoded)

```text
Body=Can you fix my broken office laptop screen?
From=+923001234567

```

#### Out-Of-Domain Fallback Sample Output (TwiML XML)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Thanks for reaching out to SafeX Solutions! I couldn't find an exact answer to that in our FAQ - let me connect you with a team member who can help. In the meantime, feel free to ask about our services, pricing, or how to get started.</Message>
</Response>

```

```

```
