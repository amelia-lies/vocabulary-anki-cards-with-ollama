# Vocab Deck Builder

Generate vocabulary flashcards using a local LLM powered by [Ollama](https://ollama.com). Build personalized vocabulary decks with duplicate detection, native Anki cloze cards, editable prompts, and a lightweight web interface for extracting vocabulary from text, URLs, and PDFs.

## Features

- **LLM-powered flashcards:** Generate definitions, multiple senses, and example sentences using a locally running language model.
- **Duplicate detection:** Identify existing vocabulary through exact matching, lemmatization, and fuzzy string matching.
- **Cloze exercises:** Generate two fill-in-the-blank exercises per basic card, with 3–4 answer options.
- **Multiple word senses:** Distinguish common meanings of polysemous words and provide separate definitions and examples for each sense.
- **Multiple input sources:** Extract vocabulary from word lists, pasted text, web articles, and PDF documents.
- **Anki export:** Export complete decks as `.apkg` files using Anki's native Cloze note type, or as `.tsv` and `.json`.
- **Editable prompts:** Customize the prompts used for flashcard generation, cloze exercises, and vocabulary extraction without modifying the source code.
- **Deck management:** Browse generated cards, preview their contents, and delete individual entries from the vocabulary database.

## Project Structure

| File | Description |
|---|---|
| `models.py` | Pydantic schemas for basic cards, cloze cards, and generation results. |
| `memory.py` | Persistent SQLite storage and duplicate detection using `simplemma` and `rapidfuzz`. |
| `generator.py` | Generates flashcards in batches through Ollama and provides existing vocabulary as context for cloze distractors. |
| `extract.py` | Extracts text from PDFs and URLs, then uses the LLM to identify candidate vocabulary. |
| `export.py` | Exports decks to Anki `.apkg`, `.tsv`, and `.json` formats. |
| `api.py` | FastAPI backend exposing the application functionality through HTTP endpoints. |
| `app_streamlit.py` | Streamlit web interface for generating, browsing, and exporting vocabulary decks. |
| `prompts_store.py` | Manages editable prompts and their default values. |
| `prompts.json` | Stores customized prompts. Created automatically when needed. |
| `vocab_memory.db` | SQLite database containing generated vocabulary and associated card data. |

## Requirements

- Python 3.10 or later.
- [Ollama](https://ollama.com) installed and running.
- A language model available locally through Ollama.

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

Download the default model:

```bash
ollama pull llama3.1:8b
```

You can use another compatible model by changing the model configuration in the application.

## Getting Started

### 1. Start the API backend

From the project directory, run:

```bash
python3 -m uvicorn api:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 2. Start the web interface

Open a second terminal in the project directory and run:

```bash
python3 -m streamlit run app_streamlit.py
```

Open `http://localhost:8501` in your browser.

Make sure Ollama is running and the selected model is available before generating cards.

## Usage

### Add vocabulary

The application supports four input methods:

1. **Word list:** Paste words or phrases, one per line.
2. **Text:** Paste a paragraph or article and let the LLM extract advanced vocabulary.
3. **URL:** Provide an article URL. The application downloads and extracts its text using `trafilatura`.
4. **PDF:** Upload a document, such as a research paper or book chapter, and extract vocabulary from its contents.

### Browse and manage your deck

Open the **My Deck** tab to browse generated vocabulary, preview definitions and examples, review cloze exercises, and export the complete deck.

Supported export formats:

- `.apkg` — Anki package ready to import.
- `.tsv` — Tab-separated text.
- `.json` — Structured vocabulary data.

You can also delete individual vocabulary entries. Deletion removes the associated database record, including its definitions, senses, examples, and cloze exercises. The term can then be generated again in a future request.

## Duplicate Detection

Vocabulary entries are stored in `vocab_memory.db`, a local SQLite database that requires no separate database server.

Before generating a new card, the application checks for duplicates in three stages:

1. **Exact matching:** Compares terms without distinguishing between uppercase and lowercase letters.
2. **Lemmatization:** Uses `simplemma` to compare normalized word forms. For example, *mitigate*, *mitigated*, and *mitigating* can be recognized as forms of the same lemma.
3. **Fuzzy matching:** Uses `rapidfuzz` to detect spelling variations, typos, and similar forms that lemmatization may not catch.

Detected duplicates are reported with the matching term and the reason for the match instead of being generated again.

The fuzzy matching threshold is configurable through `FUZZY_THRESHOLD` in `memory.py`. Its default value is `88`. Lower values make matching more permissive, potentially increasing false positives.

## Cloze Cards

Each basic vocabulary card can include two cloze exercises using Anki's native Cloze note type.

For example:

```text
The new policy helped {{c1::mitigate}} the problem.
```

Each exercise includes 3–4 answer options. Whenever possible, incorrect options are selected from the vocabulary already stored in the deck, helping create more consistent and useful practice.

Basic card generation and cloze generation use separate LLM calls. If cloze generation fails, the basic card is still saved without its cloze exercises, and the actual error is reported in the interface rather than being treated as a duplicate.

## Multiple Word Senses

The default prompt instructs the model to distinguish between words with one common meaning and genuinely polysemous words.

For example, *make up* can mean:

- To invent a story.
- To apply cosmetics.
- To constitute or form something.
- To reconcile after an argument.

When a word has multiple common meanings, the application can store them as separate senses, each with its own short label, definition, and example sentences.

Rare, archaic, or highly specialized meanings should not automatically become separate senses. This behavior can be customized through the **Prompts** tab.

## Editable Prompts

The **Prompts** tab lets you modify the three main prompts used by the application:

- Basic flashcard generation.
- Cloze exercise generation.
- Vocabulary extraction from text, URLs, and PDFs.

You can save custom prompts or restore each prompt to its default value.

Prompt configurations are stored in `prompts.json` and are created automatically when needed. Changes apply to subsequent generation requests and do not regenerate existing cards.

## Configuration and Customization

A few useful settings can be adjusted to tailor the application to your workflow:

- **LLM model:** Change the Ollama model used for vocabulary generation and extraction.
- **Fuzzy matching:** Adjust `FUZZY_THRESHOLD` in `memory.py` to control duplicate detection sensitivity.
- **Generation prompts:** Customize the card format, definitions, examples, senses, and cloze behavior through the web interface.
- **Storage:** The application uses SQLite for persistent local storage without requiring a separate database server.


## License

`MIT License`
