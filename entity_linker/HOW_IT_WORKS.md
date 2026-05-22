# How it works — simple explanation

## The big picture

Imagine you have a Macedonian recipe that says you need **"павлака"**.
You want to look that up in a huge American food database (USDA) to find its nutritional info.
But the database only has English entries, and even in English there are many types of cream —
sour cream, heavy cream, whipping cream, light cream...

The app figures out which one is the right match by going through 5 steps.
It also shows you every decision it made along the way, so nothing is a black box.

---

## Step 1 — What language is this, and what does it mean in English?

The app looks at the ingredient and asks: is this Macedonian, English, or something else?

- If it's **Macedonian** (Cyrillic letters), it translates it to English.
  - "павлака" → "sour cream"
  - "јајца" → "egg"
  - "брашно" → "wheat flour"
- If it's already **English**, it moves on as-is.

With an AI key: a language model does the translation.
Without one: the app checks a built-in Macedonian dictionary (~100 entries).

---

## Step 2 — Is this word vague or specific?

Some ingredients are very clear. "Mozzarella" can only mean one thing.
But "сирење" just means "cheese" — there are hundreds of cheeses in the database.

The app asks: *do I need more information before I can search?*

- **Specific ingredient** → skip to Step 4, search right away.
- **Vague/generic ingredient** → go to Step 3 first, get some context.

---

## Step 3 — How is this ingredient actually used in recipes? *(only for vague ones)*

The app searches through all **36,237 Macedonian recipes** to find ones that use this ingredient.
It looks at how it appears — what quantity, in what type of dish.

For example, "павлака" might appear in:
- "Chicken in creamy sauce" — *200ml павлака*
- "Cherry cake" — *125gr павлака*

This tells the app something important: if "павлака" shows up mostly in savoury sauces,
it's probably sour cream — not whipping cream or heavy cream.

---

## Step 4 — Search the USDA database

Now the app searches the USDA food database (7,793 entries) using the English translation.
It compares every word in the search query against every entry and scores them.

**How the score works — Jaccard similarity:**

Split both the query and the USDA entry into individual words, then:

```
score = (words in common) / (total unique words combined)
```

Plus a small +0.12 bonus for any shared word longer than 4 characters.

**Example with "sour cream":**

| USDA entry | In common | Total unique | Base score | Bonus | Final |
|---|---|---|---|---|---|
| Cream, sour, cultured | sour, cream (2) | sour, cream, cultured (3) | 2/3 = 0.667 | +0.12 for "cream" | **78%** |
| Sour cream, light | sour, cream (2) | sour, cream, light (3) | 2/3 = 0.667 | +0.12 for "cream" | **78%** |
| Sour cream, imitation, cultured | sour, cream (2) | sour, cream, imitation, cultured (4) | 2/4 = 0.5 | +0.12 for "cream" | **62%** |

The more extra words an entry has that you didn't search for, the lower its score.
"Cream, sour, cultured" wins because it has the fewest irrelevant words.

The top 10 results are returned.

---

## Step 5 — Pick the best one

The app now has a list of candidates. It picks the best match.

With an AI key: the AI reads the candidates, the original ingredient, and the recipe context
from Step 3, then decides which one fits best and explains its reasoning in plain text.

Without an AI key: it just picks the one with the highest score from Step 4.

The result is:
- The winning USDA entry (e.g. *Cream, sour, cultured — ID 171257*)
- A confidence level: **High** (80%+), **Medium** (55–79%), or **Low** (below 55%)
- A short explanation of why it picked that one

---

## Why does it go through all these steps instead of just searching?

Because a direct search isn't enough.

If you just search "павлака" in an English database — nothing, it's Macedonian.
If you translate it to "cream" and search — 50+ results, no way to pick.
If you translate it to "sour cream" and search — still 10 results, all similar.

The context step (Step 3) is what breaks the tie.
The AI reasoning (Step 5) is what makes the final call with an explanation.

---

## The Macedonian dictionary

Located in `agent/entity_linker.py` as a variable called `MK_DICT`.
It's a simple lookup table — Macedonian word on the left, English on the right:

```
"павлака"  →  "sour cream"
"кромид"   →  "onion raw"
"лук"      →  "garlic raw"
"јајца"    →  "egg whole raw"
"брашно"   →  "wheat flour white"
...
```

About 100 entries. If an ingredient isn't in the dictionary and there's no AI key,
it gets passed to the search untranslated — the search still tries its best.

---

## What you see on screen

Every one of these 5 steps is shown as a card on the screen.
- Green card = that step ran
- Grey card = that step was skipped (Step 3 is skipped for specific ingredients)

The tool calls (the moment the app searches recipes or searches USDA)
are shown as code blocks so you can see exactly what query was sent and what came back.
