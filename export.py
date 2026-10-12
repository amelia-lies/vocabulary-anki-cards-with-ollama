"""
Turns VocabularyCard objects into files for import into Anki:

- .apkg  - a real Anki package (genanki), with TWO note types:
           "IELTS Basic" (term -> definition + examples) and
           "IELTS Cloze" (Anki's native cloze type, so Anki's own
           scheduler treats each blank as its own card).
- .tsv   - plain Anki-importable TSV (Front/Back), kept for compatibility
           with the original script and for quick spreadsheet review.
- .json  - full structured backup, including cloze options.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import genanki

from models import VocabularyCard

# Fixed IDs so re-exporting updates the same deck/note types in Anki instead of creating duplicates
DECK_ID = 1_907_020_001
BASIC_MODEL_ID = 1_907_020_101
CLOZE_MODEL_ID = 1_907_020_102


def html_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def make_back(card: VocabularyCard) -> str:
    multi = len(card.senses) > 1
    blocks = []
    for sense in card.senses:
        header = f"<b>{sense.label}</b><br>" if multi and sense.label else ""
        blocks.append(
            f"{header}<b>Definition</b><br>{sense.definition}<br><br>"
            f"<b>Examples in context</b>{html_list(sense.examples)}"
        )
    return "<hr>".join(blocks).strip()


BASIC_MODEL = genanki.Model(
    BASIC_MODEL_ID,
    "IELTS Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        }
    ],
)

# Anki's built-in cloze template syntax: {{cloze:Text}}
CLOZE_MODEL = genanki.Model(
    CLOZE_MODEL_ID,
    "IELTS Cloze",
    fields=[{"name": "Text"}, {"name": "Options"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}<br><br>Options: {{Options}}",
            "afmt": "{{cloze:Text}}<br><br>{{Extra}}",
        }
    ],
    model_type=genanki.Model.CLOZE,
)


def _to_anki_cloze(sentence: str, answer: str) -> str:
    """Turn "The results ____ a clear trend." + "indicate" into
    Anki's {{c1::indicate}} cloze syntax."""
    if "____" in sentence:
        return sentence.replace("____", f"{{{{c1::{answer}}}}}", 1)
    # fall back: just wrap the answer wherever it appears
    return sentence.replace(answer, f"{{{{c1::{answer}}}}}", 1)


def build_apkg(cards: list[VocabularyCard], out_path: str | Path, deck_name: str) -> Path:
    deck = genanki.Deck(DECK_ID, deck_name)

    for card in cards:
        deck.add_note(
            genanki.Note(
                model=BASIC_MODEL,
                fields=[card.term, make_back(card)],
            )
        )
        for cz in card.cloze:
            options_str = " / ".join(cz.options) if cz.options else ""
            deck.add_note(
                genanki.Note(
                    model=CLOZE_MODEL,
                    fields=[
                        _to_anki_cloze(cz.sentence, cz.answer),
                        options_str,
                        f"Term: {card.term}",
                    ],
                )
            )

    out_path = Path(out_path)
    genanki.Package(deck).write_to_file(str(out_path))
    return out_path


def write_tsv(cards: list[VocabularyCard], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["Front", "Back"])
        for card in cards:
            writer.writerow([card.term, make_back(card)])
    return out_path


def write_json(cards: list[VocabularyCard], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in cards], f, ensure_ascii=False, indent=2)
    return out_path
