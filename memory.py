"""
Persistent memory of every term that has ever been turned into a card.

Two layers of duplicate detection, both free/offline:

1. Lemma matching (simplemma - pure-python, no model download) - catches
   different inflections/conjugations of the same term
   ("mitigate" / "mitigating" / "mitigated" -> same lemma sequence).
2. Fuzzy string matching (rapidfuzz) - catches near-duplicates the
   lemmatizer misses (typos, hyphenation variants, plural forms of
   multi-word collocations, British/American spelling, etc).

Everything lives in a single local SQLite file - no server, no account,
no paid API.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import simplemma
from rapidfuzz import fuzz

DEFAULT_DB_PATH = Path("vocab_memory.db")

FUZZY_THRESHOLD = 88  # 0-100, rapidfuzz.ratio


def normalize_term(term: str) -> str:
    """Lowercase + lemmatize every word in the term.

    Multi-word collocations ("play a pivotal role") are lemmatized
    word-by-word so that "played a pivotal role" / "playing a pivotal
    role" normalize to the same signature.
    """
    words = term.strip().lower().split()
    lemmas = [simplemma.lemmatize(w, lang="en") for w in words]
    return " ".join(lemmas)


@dataclass
class DuplicateHit:
    matched_term: str
    similarity: int
    reason: str  # "exact" | "lemma" | "fuzzy"


class VocabMemory:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS terms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL UNIQUE,
                    normalized TEXT NOT NULL,
                    card_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_normalized ON terms(normalized)"
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


    # Lookup
    def check(self, term: str) -> DuplicateHit | None:
        """Return the best duplicate match for `term`, if any."""
        normalized = normalize_term(term)

        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT term, normalized FROM terms").fetchall()

        best: DuplicateHit | None = None
        for existing_term, existing_norm in rows:
            if term.strip().lower() == existing_term.strip().lower():
                return DuplicateHit(existing_term, 100, "exact")
            if normalized == existing_norm:
                return DuplicateHit(existing_term, 100, "lemma")

            score = fuzz.ratio(normalized, existing_norm)
            if score >= FUZZY_THRESHOLD and (best is None or score > best.similarity):
                best = DuplicateHit(existing_term, int(score), "fuzzy")

        return best

    def filter_new(self, terms: list[str]) -> tuple[list[str], list[DuplicateHit]]:
        """Split a term list into (new_terms, duplicate_hits).

        Also guards against duplicates *within* the same batch.
        """
        new_terms: list[str] = []
        hits: list[DuplicateHit] = []
        seen_normalized: dict[str, str] = {}

        for term in terms:
            hit = self.check(term)
            if hit is not None:
                hits.append(hit)
                continue

            normalized = normalize_term(term)
            if normalized in seen_normalized:
                hits.append(DuplicateHit(seen_normalized[normalized], 100, "lemma"))
                continue

            seen_normalized[normalized] = term
            new_terms.append(term)

        return new_terms, hits


    # Writes
    def add(self, term: str, card_dict: dict) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO terms (term, normalized, card_json) "
                "VALUES (?, ?, ?)",
                (term, normalize_term(term), json.dumps(card_dict, ensure_ascii=False)),
            )
            conn.commit()

    def delete(self, term: str) -> bool:
        """Delete a term and everything generated for it (definition,
        senses, examples, cloze exercises - it's all one row).

        Matches case-insensitively on the exact stored term string.
        Returns True if a row was deleted, False if no match was found.
        """
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "DELETE FROM terms WHERE lower(term) = lower(?)", (term,)
            )
            conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------

    def all_terms(self) -> list[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT term FROM terms ORDER BY term").fetchall()
        return [r[0] for r in rows]

    def all_cards(self) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT card_json FROM terms ORDER BY id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
