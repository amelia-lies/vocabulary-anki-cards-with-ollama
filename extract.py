"""
"Capture" flow: turn a raw text / PDF / web page into a candidate term
list, ready to hand to generator.generate_deck().
"""

from __future__ import annotations

import io

from ollama import chat

from generator import MODEL
from models import ExtractedTerms
from prompts_store import load_prompts


def extract_terms_from_text(text: str, max_chars: int = 12000) -> list[str]:
    """Ask the local LLM to mine candidate vocabulary from free text."""
    trimmed = text[:max_chars]
    system_prompt = load_prompts()["extraction"]

    response = chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": trimmed},
        ],
        format=ExtractedTerms.model_json_schema(),
        options={"temperature": 0.1},
    )

    result = ExtractedTerms.model_validate_json(response.message.content)
    return result.terms


def text_from_pdf_bytes(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def text_from_url(url: str) -> str:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Could not fetch or parse: {url}")

    extracted = trafilatura.extract(downloaded)
    if not extracted:
        raise ValueError(f"No readable article text found at: {url}")

    return extracted
