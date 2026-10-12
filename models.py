from __future__ import annotations
from pydantic import BaseModel, Field


# CORE CARD SCHEMA
class Sense(BaseModel):
    """One meaning of a term.

    Most terms only need one Sense. Genuinely polysemous terms (e.g.
    "make up" = invent / apply cosmetics / constitute a whole /
    reconcile) get one Sense per COMMON meaning - the prompt tells the
    model to use judgement and skip rare/obscure meanings.
    """

    label: str = Field(
        default="",
        description=(
            "Short 2-5 word gloss identifying which meaning this is, "
            "e.g. 'cosmetics', 'invent/fabricate'. Leave empty if the "
            "term only has one common sense."
        ),
    )
    definition: str
    examples: list[str]


class ClozeCard(BaseModel):
    """A fill-in-the-blank exercise built around one target term.

    `sentence` contains the term replaced by a literal "____" marker
    (kept plain so it's easy to post-process into Anki's {{c1::...}}
    syntax later, and easy to render as a multiple-choice question in
    the web UI before that).
    """

    sentence: str
    answer: str
    options: list[str] = Field(
        default_factory=list,
        description=(
            "3-4 plausible fillers including the correct answer, in "
            "random order. Distractors should preferably be drawn from "
            "the same vocabulary set being studied."
        ),
    )


class VocabularyCard(BaseModel):
    term: str
    senses: list[Sense]
    cloze: list[ClozeCard] = Field(default_factory=list)


class VocabularyBatch(BaseModel):
    cards: list[VocabularyCard]


def coerce_card(data: dict) -> VocabularyCard:
    """Load a card dict that may be in the OLD (pre-senses) shape:
    {"term", "definition", "examples", "cloze"} - migrate it into a
    single-Sense card on the fly so old decks keep working without a
    manual migration step.
    """
    if "senses" not in data and "definition" in data:
        data = {
            "term": data["term"],
            "senses": [
                {
                    "label": "",
                    "definition": data["definition"],
                    "examples": data.get("examples", []),
                }
            ],
            "cloze": data.get("cloze", []),
        }
    return VocabularyCard.model_validate(data)



# CLOZE GENERATION (kept as a SEPARATE call from the basic card -
# asking one small local model to produce both at once in a single
# structured-output call is fragile; splitting it means a cloze
# failure never costs you the basic card too)

class ClozeBatchItem(BaseModel):
    term: str
    cloze: list[ClozeCard]


class ClozeBatchResult(BaseModel):
    items: list[ClozeBatchItem]


# TERM EXTRACTION (for "paste a text / URL / PDF" capture flow)
class ExtractedTerms(BaseModel):
    terms: list[str] = Field(
        description=(
            "Advanced/academic single words or fixed collocations found "
            "in the source text that are worth studying for IELTS "
            "Writing Task 2. Exclude basic vocabulary."
        )
    )


# DUPLICATE REPORTING
class DuplicateMatch(BaseModel):
    requested_term: str
    matched_term: str
    similarity: int  # 0-100
    reason: str  # "exact" | "lemma" | "fuzzy"


class GenerationResult(BaseModel):
    cards: list[VocabularyCard]
    skipped_duplicates: list[DuplicateMatch] = Field(default_factory=list)
    errors: list[str] = Field(
        default_factory=list,
        description=(
            "Real generation failures (e.g. the local model returned "
            "malformed JSON for a batch). Distinct from duplicates: if "
            "cards is empty AND errors is non-empty, nothing was "
            "actually a duplicate - generation failed."
        ),
    )
