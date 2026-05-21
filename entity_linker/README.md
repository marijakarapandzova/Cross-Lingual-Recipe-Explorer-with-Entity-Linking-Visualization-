# Agentic Entity Linking Explorer
**Визуелизација на агентски систем за поврзување македонски состојки → USDA FoodData Central**

Имплементација на 5-фазниот pipeline од тезата:

```
Состојка → Analyze → Decide Context → Fetch Context → Search USDA → Evaluate → USDA Ентитет
```

---

## Структура на проектот

```
entity_linker/
├── agent/
│   └── entity_linker.py      # Главен агент (5 фази + алатки)
├── api/
│   └── main.py               # FastAPI REST backend
├── ui/
│   └── app.py                # Streamlit UI
├── data/
│   └── parsed_recipes.json   # Македонскиот датасет (36,237 рецепти)
├── requirements.txt
└── README.md
```

---

## Инсталација

```bash
pip install -r requirements.txt
```

---

## Стартување

### Опција 1 — Само Streamlit (препорачано за демо)

```bash
cd entity_linker
streamlit run ui/app.py
```

Отвора се во прелистувачот на `http://localhost:8501`.

### Опција 2 — FastAPI backend + Streamlit

Терминал 1:
```bash
cd entity_linker
uvicorn api.main:app --reload --port 8000
```

Терминал 2:
```bash
streamlit run ui/app.py
```

API документација: `http://localhost:8000/docs`

---

## Конфигурација

### OpenAI API Key (за LLM reasoning)

```bash
export OPENAI_API_KEY="sk-..."
```

Без API key апликацијата работи со **rule-based fallback** — јазична детекција преку Кирилица, хевристики за двосмисленост, и keyword-based USDA пребарување. Сите 5 фази се прикажуваат и без LLM.

### Со OpenAI

Со API key агентот користи `gpt-4o-mini` за:
- Детекција на јазик + превод
- Одлука за потреба од контекст
- Формулирање на USDA query
- Евалуација и избор на кандидат со reasoning

---

## API Endpoints

| Endpoint | Опис |
|---|---|
| `GET /recipes?q=пилешко&limit=20` | Пребарување рецепти |
| `GET /recipes/{index}` | Детали за рецепт |
| `GET /link/ingredient?name=павлака` | Линкување поединечна состојка |
| `GET /link/recipe/{index}` | Линкување целосен рецепт |
| `GET /stats` | Статистики за датасетот |

---

## Архитектура на агентот

### Алатки (Tools)

**`get_recipe_context(ingredient, top_k)`**
- Пребарува во `parsed_recipes.json`
- Враќа рецепти кои ја содржат состојката
- Обезбедува culinary контекст за двосмислени термини

**`search_usda_classes(query, top_k)`**
- Пребарува USDA FoodData Central база
- Во демо: keyword overlap scoring
- Во продукција: FAISS + Sentence-BERT embeddings

### Reasoning trace

За секоја состојка агентот враќа:
```python
AgentTrace(
    ingredient_original = "павлака",
    detected_language   = "mk",
    english_translation = "cream",
    is_ambiguous        = True,
    needs_context       = True,
    context_recipes     = [...],     # рецепти за контекст
    search_query        = "heavy cream cooking",
    tool_calls          = [...],     # сите повици на алатки
    candidates          = [...],     # USDA кандидати со scores
    selected_usda_id    = "172185",
    selected_usda_name  = "Cream, fluid, heavy whipping",
    confidence          = 87,
    confidence_level    = "high",
    reasoning           = "Context shows usage in savory soups ...",
    processing_time_ms  = 1240,
)
```

---

## Продукциски проширувања

За полна продукциска имплементација:

1. **Semantic USDA search** — заменете го `USDASearchTool` со FAISS индекс:
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer("all-MiniLM-L6-v2")
   # encode USDA descriptions → store in FAISS
   ```

2. **LangGraph state management** — замена на рачниот pipeline со LangGraph StateGraph

3. **Batch processing** — за bulk linking на сите 36,237 рецепти:
   ```bash
   python -m agent.batch_link --input data/parsed_recipes.json --output data/linked.json
   ```

4. **Caching** — Redis cache за веќе линкувани состојки
