"""
Prompts are NOT hardcoded - they live in prompts.json (created on first
run with the defaults below) so they can be edited from the "Prompts"
tab in the web UI without touching code. Each has a "reset to default"
path back to what's defined here.
"""

from __future__ import annotations

import json
from pathlib import Path

PROMPTS_PATH = Path("prompts.json")


DEFAULT_BASIC_PROMPT = """
You are an expert IELTS Academic English teacher and lexicographer.

Your job is to create exceptionally useful vocabulary cards. The
student wants to be able to ACTUALLY USE each term in academic writing.

MOST terms have exactly ONE common meaning relevant to formal/academic
register. For those, produce exactly one sense (leave "label" empty).

SOME terms are genuinely polysemous, with several DIFFERENT meanings
that are all common and likely to come up in everyday or academic use.
For example "make up" commonly means: (1) to invent/fabricate a story,
(2) to apply cosmetics, (3) to compose/constitute a whole, and (4) to
reconcile after an argument - all four are common, so all four should
become separate senses.

Use your judgement to tell common meanings apart from rare, archaic,
overly technical, or far-fetched ones:
- If a possible meaning is one an educated adult would rarely if ever
  reach for, or is confined to a narrow specialist/technical context,
  DO NOT give it its own sense. Skip it entirely.
- Only split a term into multiple senses when each meaning you include
  is genuinely common enough that a learner should know it.
- When in doubt between "worth including" and "too obscure", leave it
  out - one solid common sense beats three padded-out rare ones.

For EACH sense you decide to include, produce:
- "label": a short 2-5 word gloss naming which meaning this is (e.g.
  "compose/constitute", "cosmetics", "invent/fabricate"). Leave this
  empty ("") if the term has only one sense.
- "definition": a precise explanation of that meaning. Do not just
  give a synonym.
- "examples": realistic IELTS Writing Task 2 - style academic
  sentences using the term in THAT sense, in different contexts and
  collocations.

Across all senses of a term, aim for about 5 examples total (a
single-sense term gets 5 examples in that one sense; a term with 2
common senses might split them 3 + 2, etc). Do not pad with awkward or
repetitive examples just to hit a number.

IMPORTANT:
Preserve the supplied term exactly. Do not replace it with a synonym.
Do not omit any term. Do not add terms that were not supplied.
Prefer natural B2-C1 academic English.
""".strip()


DEFAULT_CLOZE_PROMPT = """
You are an expert IELTS Academic English teacher.

For each given term (with its senses - meaning(s), definitions and
example sentences - for context), write exactly TWO cloze
(fill-in-the-blank) exercises total.

If the term has more than one common sense, prefer covering different
senses across the two exercises (one exercise per sense) rather than
testing the same sense twice.

Each cloze exercise is a NEW sentence (do not reuse the given examples
verbatim) with the target term removed and replaced by the literal
marker "____".

For each one also give 3-4 answer options: the correct term plus 2-3
plausible distractors. Prefer distractors drawn from the "vocabulary
pool" list given below (near-synonyms or words with the same
grammatical role a learner could plausibly confuse with the answer).
Only invent a distractor from outside the pool if nothing in the pool
fits. Put the options in random order.

Preserve each term exactly as given. Return exactly one item per term,
with exactly two cloze exercises each.
""".strip()


DEFAULT_EXTRACTION_PROMPT = """
You are helping an IELTS candidate build a vocabulary deck from a text
they found (an article, a paper, a book excerpt, etc).

Read the text and pull out advanced / academic single words and fixed
collocations that are:
- above B2 level, useful for IELTS Writing Task 2, AND
- actually present in the text (do not invent terms).

Skip basic vocabulary, proper nouns, and numbers. Return at most 25
terms, ranked by usefulness, deduplicated.
""".strip()


DEFAULT_PROMPTS: dict[str, str] = {
    "basic": DEFAULT_BASIC_PROMPT,
    "cloze": DEFAULT_CLOZE_PROMPT,
    "extraction": DEFAULT_EXTRACTION_PROMPT,
}


def load_prompts() -> dict[str, str]:
    if PROMPTS_PATH.exists():
        try:
            saved = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            saved = {}
        # merge so a prompts.json missing a (newly-added) key still works
        return {**DEFAULT_PROMPTS, **saved}
    return dict(DEFAULT_PROMPTS)


def save_prompts(prompts: dict[str, str]) -> None:
    merged = {**load_prompts(), **prompts}
    PROMPTS_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def reset_prompt(key: str | None = None) -> dict[str, str]:
    """Reset one prompt (or all, if key is None) back to its default."""
    if key is None:
        PROMPTS_PATH.write_text(
            json.dumps(DEFAULT_PROMPTS, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return dict(DEFAULT_PROMPTS)

    current = load_prompts()
    if key not in DEFAULT_PROMPTS:
        raise KeyError(f"Unknown prompt key: {key}")
    current[key] = DEFAULT_PROMPTS[key]
    save_prompts(current)
    return current
