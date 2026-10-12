"""
Lightweight web UI on top of api.py.

Run with:
    streamlit run app_streamlit.py
"""

from __future__ import annotations

import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="Vocab Deck Builder", page_icon="📚", layout="wide")
st.title("📚 Vocab Deck Builder")
st.caption("Word: Example")

tab_terms, tab_text, tab_url, tab_pdf, tab_deck, tab_prompts = st.tabs(
    ["Word list", "Paste text", "From URL", "From PDF", "My deck", "Prompts"]
)


def _post(endpoint: str, json_body: dict | None = None, files=None):
    try:
        resp = requests.post(f"{API}{endpoint}", json=json_body, files=files, timeout=600)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")  # type: ignore[union-attr]
        except Exception:
            pass
        st.error(f"Request failed: {detail or e}")
        return None


def _show_card(card: dict):
    senses = card.get("senses") or []
    multi = len(senses) > 1
    for sense in senses:
        if multi and sense.get("label"):
            st.markdown(f"**Sense: {sense['label']}**")
        st.markdown(f"**Definition:** {sense['definition']}")
        st.markdown("**Examples:**")
        for ex in sense["examples"]:
            st.markdown(f"- {ex}")
        if multi:
            st.divider()

    if card.get("cloze"):
        st.markdown("**Cloze practice:**")
        for cz in card["cloze"]:
            st.markdown(f"- {cz['sentence']}")
            st.caption("Options: " + " / ".join(cz.get("options", [])))
    else:
        st.caption("(no cloze exercises for this card)")


def _show_result(result: dict):
    cards = result.get("cards", [])
    skipped = result.get("skipped_duplicates", [])
    errors = result.get("errors", [])

    if cards:
        st.success(f"Generated {len(cards)} new card(s).")
        for card in cards:
            with st.expander(card["term"]):
                _show_card(card)
    elif skipped and not errors:
        st.info("No new cards generated: everything requested was a duplicate (see below).")
    elif errors:
        st.error("No cards were generated: generation failed (NOT a duplicate issue)")
    else:
        st.warning("No cards were generated and no cause was reported. Check the backend terminal.")

    if errors:
        st.error(f"{len(errors)} generation error(s):")
        for e in errors:
            st.code(e)
        st.caption(
            "This usually means the local model returned output that didn't match the "
            "expected format for that batch. Try again, or generate fewer terms at once."
        )

    if skipped:
        st.warning(f"Skipped {len(skipped)} duplicate(s):")
        for s in skipped:
            label = f"already have **{s['matched_term']}**" if s["matched_term"] else "already in deck"
            st.markdown(
                f"- `{s['requested_term']}` -> {label} "
                f"({s['reason']}, {s['similarity']}% match)"
            )


with tab_terms:
    st.subheader("Generate from a word list")
    raw = st.text_area(
        "One term per line (single words or fixed collocations):",
        height=150,
        placeholder="mitigate\nmake up\nnotwithstanding",
    )
    if st.button("Generate cards", key="btn_terms"):
        terms = [t.strip() for t in raw.splitlines() if t.strip()]
        result = _post("/generate/terms", {"terms": terms})
        if result:
            _show_result(result)

with tab_text:
    st.subheader("Paste any text")
    st.caption("The vocabulary is mined automatically from the text you paste.")
    text = st.text_area("Paste an article, paragraph, essay, etc:", height=200)
    if st.button("Extract & generate", key="btn_text"):
        result = _post("/generate/text", {"text": text})
        if result:
            _show_result(result)

with tab_url:
    st.subheader("Capture from a web page")
    url = st.text_input("URL", placeholder="https://...")
    if st.button("Fetch & generate", key="btn_url"):
        result = _post("/generate/url", {"url": url})
        if result:
            _show_result(result)

with tab_pdf:
    st.subheader("Capture from a PDF")
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded and st.button("Extract & generate", key="btn_pdf"):
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        result = _post("/generate/pdf", files=files)
        if result:
            _show_result(result)

with tab_deck:
    st.subheader("My deck")
    try:
        cards = requests.get(f"{API}/deck", timeout=30).json()
    except requests.RequestException:
        cards = None
        st.error("Backend not reachable at " + API)

    if cards is not None:
        st.write(f"**{len(cards)} term(s) so far**")

        st.divider()
        st.subheader("Browse / delete a word")
        if cards:
            terms_list = [c["term"] for c in cards]
            picked = st.selectbox("Term", terms_list, key="deck_pick")
            picked_card = next((c for c in cards if c["term"] == picked), None)
            if picked_card:
                with st.expander(f"Preview: {picked}", expanded=True):
                    _show_card(picked_card)

                st.warning(
                    f"Deleting **{picked}** removes its definition(s), examples AND cloze "
                    "exercises, and frees the word up to be generated again later."
                )
                confirm = st.checkbox(f"Yes, delete '{picked}'", key="deck_confirm")
                if st.button("🗑️ Delete this word", disabled=not confirm, key="deck_delete_btn"):
                    resp = requests.post(f"{API}/deck/delete", json={"term": picked}, timeout=30)
                    if resp.ok:
                        st.success(f"Deleted '{picked}'.")
                        st.rerun()
                    else:
                        st.error(f"Could not delete: {resp.text}")
        else:
            st.write("Empty so far.")

        st.divider()
        st.subheader("Export")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.link_button("⬇️ Download .apkg (Anki)", f"{API}/export/apkg")
        with c2:
            st.link_button("⬇️ Download .tsv", f"{API}/export/tsv")
        with c3:
            st.link_button("⬇️ Download .json", f"{API}/export/json")

with tab_prompts:
    st.subheader("Edit prompts")
    st.caption(
        "These are the instructions sent to the local model. Changes apply "
        "to the NEXT generation you run - already-generated cards are not "
        "regenerated automatically."
    )

    try:
        prompts = requests.get(f"{API}/prompts", timeout=30).json()
    except requests.RequestException:
        prompts = None
        st.error("Backend not reachable at " + API)

    if prompts is not None:
        labels = {
            "basic": "Basic card prompt (definitions & examples, incl. multi-sense handling)",
            "cloze": "Cloze exercise prompt",
            "extraction": "Term-extraction prompt (used for paste-text / URL / PDF capture)",
        }
        for key, label in labels.items():
            st.markdown(f"### {label}")
            edited = st.text_area(
                label,
                value=prompts.get(key, ""),
                height=260,
                key=f"prompt_{key}",
                label_visibility="collapsed",
            )
            col_save, col_reset = st.columns([1, 1])
            with col_save:
                if st.button("💾 Save", key=f"save_{key}"):
                    resp = requests.post(f"{API}/prompts", json={key: edited}, timeout=30)
                    if resp.ok:
                        st.success("Saved.")
                    else:
                        st.error(f"Could not save: {resp.text}")
            with col_reset:
                if st.button("↩️ Reset to default", key=f"reset_{key}"):
                    resp = requests.post(f"{API}/prompts/reset", json={"key": key}, timeout=30)
                    if resp.ok:
                        st.success("Reset to default.")
                        st.rerun()
                    else:
                        st.error(f"Could not reset: {resp.text}")
            st.divider()
