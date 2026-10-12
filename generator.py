from __future__ import annotations
import json
from ollama import chat
from memory import VocabMemory, normalize_term
from models import (
    ClozeBatchResult,
    DuplicateMatch,
    GenerationResult,
    VocabularyBatch,
    VocabularyCard,
)
from prompts_store import load_prompts

MODEL = "llama3.1:8b"
BATCH_SIZE = 8


# STEP 1 basic card: term -> one or more senses (definition + examples each). 
# Kept as its own structured-output call, separate from cloze, 
# because local 8B models handle a smaller schema more reliably.


def generate_basic_batch(terms: list[str]) -> list[VocabularyCard]:
    system_prompt = load_prompts()["basic"]
    prompt = f"""
{system_prompt}

Generate cards for exactly these terms:

{json.dumps(terms, indent=2, ensure_ascii=False)}

Return one card for every term.
"""
    response = chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        format=VocabularyBatch.model_json_schema(),
        options={"temperature": 0.15},
    )
    result = VocabularyBatch.model_validate_json(response.message.content)
    return result.cards



# STEP 2 cloze exercises, generated separately per batch

def generate_cloze_batch(
    cards: list[VocabularyCard], vocabulary_pool: list[str]
) -> dict[str, list]:
    system_prompt = load_prompts()["cloze"]

    payload = [
        {
            "term": c.term,
            "senses": [
                {"label": s.label, "definition": s.definition, "examples": s.examples}
                for s in c.senses
            ],
        }
        for c in cards
    ]
    pool_block = (
        json.dumps(vocabulary_pool, ensure_ascii=False, indent=2)
        if vocabulary_pool
        else "[]  (empty so far - invent sensible distractors)"
    )
    prompt = f"""
{system_prompt}

Vocabulary pool (existing deck - prefer these for distractor options):

{pool_block}

Terms:

{json.dumps(payload, indent=2, ensure_ascii=False)}
"""
    response = chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        format=ClozeBatchResult.model_json_schema(),
        options={"temperature": 0.2},
    )
    result = ClozeBatchResult.model_validate_json(response.message.content)
    return {item.term: item.cloze for item in result.items}


# ----
# Pipeline
# ----


def generate_deck(
    terms: list[str],
    memory: VocabMemory,
    batch_size: int = BATCH_SIZE,
    progress_cb=None,
) -> GenerationResult:
    """Full pipeline: dedup against memory, generate in batches, persist.

    Basic cards and cloze exercises are generated in two separate
    structured-output calls per batch. If the cloze call fails, the
    basic cards are still kept (with an empty `cloze` list) and the
    failure is reported in `errors` - it is never silently reported
    as "duplicate".
    """
    new_terms, _ = memory.filter_new(terms)

    # Explicit, human-readable mapping of skipped (ACTUAL duplicate) terms.
    skipped: list[DuplicateMatch] = []
    seen_normalized: dict[str, str] = {}

    for term in terms:
        if term in new_terms:
            seen_normalized[normalize_term(term)] = term
            continue
        hit = memory.check(term)
        if hit is None:
            norm = normalize_term(term)
            hit_term = seen_normalized.get(norm, "(earlier duplicate in this request)")
            skipped.append(
                DuplicateMatch(requested_term=term, matched_term=hit_term, similarity=100, reason="lemma")
            )
        else:
            skipped.append(
                DuplicateMatch(
                    requested_term=term,
                    matched_term=hit.matched_term,
                    similarity=hit.similarity,
                    reason=hit.reason,
                )
            )

    all_cards: list[VocabularyCard] = []
    errors: list[str] = []
    vocabulary_pool = memory.all_terms()

    for start in range(0, len(new_terms), batch_size):
        batch = new_terms[start : start + batch_size]

        try:
            cards = generate_basic_batch(batch)
        except Exception as error:  # noqa: BLE001 - surface to caller, keep going
            msg = f"Failed to generate basic cards for {batch}: {error}"
            errors.append(msg)
            if progress_cb:
                progress_cb("ERROR: " + msg)
            continue

        '''# Cloze is best-effort: never lose the basic card if this fails.
        try:
            cloze_by_term = generate_cloze_batch(cards, vocabulary_pool)
            for card in cards:
                card.cloze = cloze_by_term.get(card.term, [])
        except Exception as error:  # noqa: BLE001
            msg = f"Cloze generation failed for {[c.term for c in cards]}: {error}"
            errors.append(msg)
            if progress_cb:
                progress_cb("ERROR: " + msg)
            # cards keep cloze=[] and are still saved below'''

        for card in cards:
            memory.add(card.term, card.model_dump())
            vocabulary_pool.append(card.term)

        all_cards.extend(cards)

        if progress_cb:
            progress_cb(f"Generated {len(cards)} card(s) for: {', '.join(batch)}")

    return GenerationResult(cards=all_cards, skipped_duplicates=skipped, errors=errors)
