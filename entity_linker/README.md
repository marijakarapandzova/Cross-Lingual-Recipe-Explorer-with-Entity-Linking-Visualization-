# Agentic Entity Linking Explorer

A visualization tool for an LLM-driven agentic entity linking system that maps Macedonian food ingredients to standardized entries in the USDA FoodData Central database. Built as a wrapper around the pipeline described in *Chapter 3.2 — LLM-Driven Agentic Entity Linking* of the thesis by Darko Gjorgjievski.

---

## What it does

The application takes a Macedonian recipe and answers one question for each ingredient: *which USDA food entity does this ingredient correspond to?*

Matching is non-trivial because:
- Ingredients are written in Macedonian (Cyrillic script)
- Generic terms like **павлака** ("cream") map to several distinct USDA entries depending on culinary context
- The USDA database uses standardized English descriptions that differ from how ingredients appear in recipes

The app solves this through a **5-stage agentic pipeline** and makes every reasoning step visible to the user, so you can see exactly how the agent arrived at each decision.

---

## The 5-stage pipeline

Every ingredient passes through the same pipeline. Each stage is shown on screen as a colour-coded card.

### Stage 1 — Analyze
Detects the language of the ingredient and translates it to English if needed.

- If an LLM is configured, it calls the model and asks for the BCP-47 language code and an English translation.
- Without an LLM, Cyrillic detection triggers a lookup in a built-in Macedonian-to-English dictionary (`MK_DICT`, ~100 entries). Multi-word and prefix matches are tried before falling back to token-level matching.
- Output: detected language (e.g. `mk`) and English translation (e.g. `sour cream`).

### Stage 2 — Decide Context
Decides whether the ingredient is ambiguous enough to require recipe context for disambiguation.

- With an LLM: the model reasons about whether the English translation maps to multiple distinct USDA categories (e.g. "cream" → heavy cream / sour cream / light cream / whipping cream).
- Without an LLM: checks the translation against a hardcoded set of generic terms (`oil`, `cheese`, `meat`, `cream`, `pepper`, etc.).
- Output: `needs_context = true/false` with a short reason.

### Stage 3 — Fetch Context *(conditional)*
Only runs when Stage 2 decided context is needed.

Calls the **`get_recipe_context`** tool, which searches the full Macedonian recipe dataset (36,237 recipes) for recipes that contain the ingredient. It uses the *original language* ingredient name for matching to preserve linguistic specificity. Returns up to 5 recipes with the ingredient's quantity and name as it appears in each recipe.

This step grounds the agent: instead of guessing that "павлака" means sour cream in all cases, it sees how the ingredient is actually used in Macedonian cooking.

### Stage 4 — Search USDA
Calls the **`search_usda_classes`** tool to retrieve candidate USDA food entries.

- The search query is the English translation from Stage 1. If context was fetched, an LLM optionally refines the query first (e.g. "sour cream" might become "sour cream cultured dairy" based on recipe context).
- The tool runs keyword + Jaccard similarity scoring across all **7,793 entries** in the USDA FoodData Central database (`usdaClasses.csv`). Tokens are extracted from both query and entry name; the score is `overlap / union`, with a small boost for long shared tokens.
- Returns the top 10 ranked candidates with their USDA IDs and similarity scores.

### Stage 5 — Evaluate & Select
Picks the best candidate from Stage 4.

- With an LLM: presents all candidates alongside the original ingredient, translation, and recipe context. The model selects the best match by index and returns a confidence score (0–100) and a written justification.
- Without an LLM: selects the candidate with the highest similarity score from Stage 4. Confidence is derived from that score.
- Output: the winning USDA ID and name, a confidence percentage, a confidence level (`high` / `med` / `low`), and a reasoning string.

---

## What you see on screen

### Single Ingredient Analysis
Type any ingredient (Macedonian or English) in the sidebar and click **Analyze**. The main area shows:

- Language flag and detected language
- Processing time in milliseconds
- All 5 stage cards in order, each colour-coded green (executed) or grey (skipped)
- The `get_recipe_context()` and `search_usda_classes()` tool calls shown as code blocks with their exact arguments and return summaries
- Context recipes in yellow cards showing recipe title and the ingredient's quantity/name from that recipe
- USDA candidates in a ranked list with similarity percentages; the selected entry highlighted in green
- Final USDA badge (`USDA:171257`) with full name
- Confidence bar (green = high, yellow = medium, red = low) with percentage
- Expandable **Agent's Reasoning** section with the LLM's written justification

### Full Recipe Analysis
Select a recipe from the sidebar dropdown (or search by title/tag). The main area shows:

- Recipe header with title, clickable tag buttons, source link, and image
- Expandable **Instructions** section
- **Ingredients** table with quantity and name
- **Analyze All Ingredients** button — runs the full pipeline on every ingredient in sequence, then shows:
  - A summary table: ingredient name → USDA entity → USDA ID → confidence emoji (🟢🟡🔴)
  - Individual expandable reasoning traces for every ingredient

### Recipe Browser
Clicking any tag button filters the recipe list to show all recipes with that tag in a 3-column grid with images, tag summaries, and ingredient counts. Clicking **View Recipe** loads that recipe into the main analysis view.

---

## LLM configuration

The app works in three modes depending on what API keys are provided in the sidebar:

| Mode | How to enable | What changes |
|---|---|---|
| **Claude (Anthropic)** | Enter Anthropic API key | Stages 1, 2, 4 (query refinement), and 5 use Claude Haiku for translation, ambiguity reasoning, query formulation, and candidate evaluation with written justification |
| **OpenAI** | Enter OpenAI API key (no Anthropic key set) | Same stages use GPT-3.5-turbo |
| **Rule-based fallback** | No API key | Stage 1 uses the Macedonian dictionary; Stage 2 uses generic-term heuristics; Stage 4 uses the raw English translation as query; Stage 5 picks the top keyword match. All 5 stages still execute and display. |

The sidebar shows which mode is active as a status badge. API keys are never stored — they live only in the running session.

---

## Data sources

| Source | Size | Purpose |
|---|---|---|
| `data/parsed_recipes.json` | 36,237 Macedonian recipes | Recipe context retrieval (Stage 3) |
| `usdaClasses.csv` | 7,793 food entries | USDA candidate search (Stage 4) |

---

## Project structure

```
entity_linker/
├── agent/
│   └── entity_linker.py      # 5-stage pipeline, USDA search, recipe context tool
├── api/
│   └── main.py               # FastAPI REST backend (optional)
├── ui/
│   └── app.py                # Streamlit visualization UI
├── data/
│   └── parsed_recipes.json   # Macedonian recipe dataset
├── usdaClasses.csv           # USDA FoodData Central entries
├── requirements.txt
└── README.md
```

---

## Running the app

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Start the Streamlit UI:**
```bash
cd entity_linker
streamlit run ui/app.py
```

Opens at `http://localhost:8501`.

**Optional — start the FastAPI backend separately:**
```bash
uvicorn api.main:app --reload --port 8000
```

REST API docs at `http://localhost:8000/docs`.

---

## REST API endpoints

| Endpoint | Description |
|---|---|
| `GET /recipes?q=пилешко&limit=20` | Search recipes by title or tag |
| `GET /recipes/{index}` | Get a single recipe by dataset index |
| `GET /link/ingredient?name=павлака` | Run the full pipeline on one ingredient |
| `GET /link/recipe/{index}` | Run the pipeline on every ingredient in a recipe |
| `GET /stats` | Dataset statistics (total recipes, top tags) |
