"""
FastAPI backend.

Run with:
    uvicorn api:app --reload --port 8000

Endpoints:
    POST /generate/terms   {"terms": [...]}                  -> GenerationResult
    POST /generate/text    {"text": "..."}                   -> GenerationResult
    POST /generate/url     {"url": "..."}                    -> GenerationResult
    POST /generate/pdf     multipart file upload              -> GenerationResult
    GET  /deck             -> full memory (all cards ever generated)
    GET  /deck/terms       -> just the term strings
    POST /deck/delete      {"term": "..."}                   -> {"deleted": bool}
    GET  /export/apkg      -> download Anki .apkg of the whole deck
    GET  /export/tsv       -> download .tsv of the whole deck
    GET  /export/json      -> download .json of the whole deck
    GET  /prompts          -> current prompts {basic, cloze, extraction}
    POST /prompts          -> partial update, persisted to prompts.json
    POST /prompts/reset    {"key": "basic" | "cloze" | "extraction" | null}
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import export
import prompts_store
from extract import extract_terms_from_text, text_from_pdf_bytes, text_from_url
from generator import generate_deck
from memory import VocabMemory
from models import GenerationResult, VocabularyCard, coerce_card

app = FastAPI(title="IELTS Vocab Deck Builder")

# Wide-open CORS for local dev with a Streamlit/React frontend on another port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = VocabMemory()
EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)


class TermsRequest(BaseModel):
    terms: list[str]


class TextRequest(BaseModel):
    text: str


class UrlRequest(BaseModel):
    url: str


class DeleteRequest(BaseModel):
    term: str


class PromptsUpdate(BaseModel):
    basic: str | None = None
    cloze: str | None = None
    extraction: str | None = None


class PromptResetRequest(BaseModel):
    key: str | None = None  # None = reset all


def _run(terms: list[str]) -> GenerationResult:
    if not terms:
        raise HTTPException(400, "No terms found/provided.")
    # progress_cb=print -> batch-by-batch progress and any real generation
    # errors show up in the `uvicorn` console, in addition to being
    # returned in the response's `errors` field.
    return generate_deck(terms, memory, progress_cb=print)


@app.post("/generate/terms", response_model=GenerationResult)
def generate_from_terms(req: TermsRequest):
    return _run(req.terms)


@app.post("/generate/text", response_model=GenerationResult)
def generate_from_text(req: TextRequest):
    terms = extract_terms_from_text(req.text)
    return _run(terms)


@app.post("/generate/url", response_model=GenerationResult)
def generate_from_url(req: UrlRequest):
    try:
        page_text = text_from_url(req.url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    terms = extract_terms_from_text(page_text)
    return _run(terms)


@app.post("/generate/pdf", response_model=GenerationResult)
async def generate_from_pdf(file: UploadFile = File(...)):
    data = await file.read()
    page_text = text_from_pdf_bytes(data)
    terms = extract_terms_from_text(page_text)
    return _run(terms)


# ------------------------------------------------------------
# Deck management
# ------------------------------------------------------------


@app.get("/deck")
def get_deck() -> list[dict]:
    return memory.all_cards()


@app.get("/deck/terms")
def get_deck_terms() -> list[str]:
    return memory.all_terms()


@app.post("/deck/delete")
def delete_term(req: DeleteRequest) -> dict:
    """Delete a term and everything generated for it (definition/senses,
    examples, cloze exercises - stored as one row, so one delete removes
    all of it). Also frees that word up to be regenerated fresh later."""
    deleted = memory.delete(req.term)
    if not deleted:
        raise HTTPException(404, f"Term not found: {req.term!r}")
    return {"deleted": True, "term": req.term}


def _all_cards_as_models() -> list[VocabularyCard]:
    return [coerce_card(c) for c in memory.all_cards()]


@app.get("/export/apkg")
def export_apkg():
    cards = _all_cards_as_models()
    if not cards:
        raise HTTPException(400, "Deck is empty.")
    path = export.build_apkg(cards, EXPORT_DIR / "IELTS_vocab.apkg", "IELTS Vocabulary")
    return FileResponse(path, filename="IELTS_vocab.apkg")


@app.get("/export/tsv")
def export_tsv():
    cards = _all_cards_as_models()
    if not cards:
        raise HTTPException(400, "Deck is empty.")
    path = export.write_tsv(cards, EXPORT_DIR / "IELTS_vocab.tsv")
    return FileResponse(path, filename="IELTS_vocab.tsv")


@app.get("/export/json")
def export_json():
    cards = _all_cards_as_models()
    if not cards:
        raise HTTPException(400, "Deck is empty.")
    path = export.write_json(cards, EXPORT_DIR / "IELTS_vocab.json")
    return FileResponse(path, filename="IELTS_vocab.json")


# ------------------------------------------------------------
# Editable prompts
# ------------------------------------------------------------


@app.get("/prompts")
def get_prompts() -> dict:
    return prompts_store.load_prompts()


@app.post("/prompts")
def update_prompts(update: PromptsUpdate) -> dict:
    data = update.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, "No prompt fields provided.")
    prompts_store.save_prompts(data)
    return prompts_store.load_prompts()


@app.post("/prompts/reset")
def reset_prompts(req: PromptResetRequest) -> dict:
    try:
        return prompts_store.reset_prompt(req.key)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
