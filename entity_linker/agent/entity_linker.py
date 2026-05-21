"""
Agentic Entity Linking Agent
Implements the 5-stage pipeline from the thesis:
  1. Analyze  (language detection + translation)
  2. Decide Context (ambiguity check)
  3. Fetch Context (recipe co-occurrence, conditional)
  4. Search USDA (keyword similarity – or FAISS in production)
  5. Evaluate & Select (LLM reasoning – or heuristic fallback)

Dependencies:
  - openai  (optional – falls back to rule-based if not installed / no key)
  - All other logic uses only the Python stdlib + the parsed_recipes.json dataset.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional

# OpenAI is optional
try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    name: str
    args: dict
    result_summary: str


@dataclass
class ContextRecipe:
    title: str
    usage_note: str


@dataclass
class USDACandidate:
    usda_id: str
    name: str
    score: float
    selected: bool = False


@dataclass
class AgentTrace:
    ingredient_original: str
    detected_language: str
    english_translation: str
    is_ambiguous: bool = False
    needs_context: bool = False
    context_recipes: list[ContextRecipe] = field(default_factory=list)
    search_query: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    candidates: list[USDACandidate] = field(default_factory=list)
    selected_usda_id: Optional[str] = None
    selected_usda_name: Optional[str] = None
    confidence: int = 0
    confidence_level: str = "low"
    reasoning: str = ""
    stages_completed: list[str] = field(default_factory=list)
    processing_time_ms: int = 0


# ---------------------------------------------------------------------------
# Recipe context tool
# ---------------------------------------------------------------------------

class RecipeContextTool:
    def __init__(self, recipes_path: str):
        print("Loading recipe dataset …", flush=True)
        with open(recipes_path, encoding="utf-8") as f:
            self.recipes: list[dict] = json.load(f)
        print(f"  → {len(self.recipes):,} recipes loaded", flush=True)

    def search(self, ingredient_name: str, top_k: int = 5) -> list[ContextRecipe]:
        needle = ingredient_name.lower().strip()
        matches: list[tuple[dict, str]] = []
        for recipe in self.recipes:
            for ing in recipe.get("ingredients", []):
                ing_name = ing.get("name", "").lower()
                if needle in ing_name or ing_name in needle:
                    qty = f"{ing.get('quantity', '')} {ing.get('unit', '')}".strip()
                    usage = f"{qty} — {ing.get('name', '')}" if qty else ing.get("name", "")
                    matches.append((recipe, usage))
                    break
        random.shuffle(matches)
        return [
            ContextRecipe(title=r.get("title", "Непознат рецепт"), usage_note=u)
            for r, u in matches[:top_k]
        ]


# ---------------------------------------------------------------------------
# USDA database (curated subset; replace with FAISS index in production)
# ---------------------------------------------------------------------------

USDA_DATABASE = [
    {"id": "171284", "name": "Yogurt, Greek, plain, nonfat"},
    {"id": "171285", "name": "Yogurt, Greek, plain, whole milk"},
    {"id": "175213", "name": "Yogurt, plain, low fat"},
    {"id": "171254", "name": "Milk, whole, 3.25% milkfat"},
    {"id": "173420", "name": "Cheese, feta"},
    {"id": "173419", "name": "Cheese, mozzarella, whole milk"},
    {"id": "173417", "name": "Cheese, cheddar"},
    {"id": "171401", "name": "Lard"},
    {"id": "173577", "name": "Oil, animal, dripping or drippings"},
    {"id": "173410", "name": "Butter, salted"},
    {"id": "172185", "name": "Cream, fluid, heavy whipping"},
    {"id": "172186", "name": "Cream, sour, cultured"},
    {"id": "172187", "name": "Cream, light, coffee cream"},
    {"id": "174639", "name": "Pork, cured, ham, extra lean, roasted"},
    {"id": "167897", "name": "Pork, cured, bacon, cooked, pan-fried"},
    {"id": "174608", "name": "Pork, cured, separable fat, unheated"},
    {"id": "174624", "name": "Pork, fresh, ground, raw"},
    {"id": "171791", "name": "Beef, ground, 80% lean meat / 20% fat, raw"},
    {"id": "174946", "name": "Lamb, ground, raw"},
    {"id": "171507", "name": "Chicken, broilers or fryers, breast, raw"},
    {"id": "170000", "name": "Onions, raw"},
    {"id": "170457", "name": "Tomatoes, red, ripe, raw"},
    {"id": "168409", "name": "Cucumber, with peel, raw"},
    {"id": "170108", "name": "Peppers, sweet, green, raw"},
    {"id": "170931", "name": "Peppers, sweet, red, raw"},
    {"id": "168586", "name": "Peppers, chili, red, raw"},
    {"id": "171329", "name": "Spices, paprika"},
    {"id": "170918", "name": "Garlic, raw"},
    {"id": "170393", "name": "Celery, raw"},
    {"id": "169276", "name": "Potatoes, flesh and skin, raw"},
    {"id": "170302", "name": "Carrots, raw"},
    {"id": "170379", "name": "Spinach, raw"},
    {"id": "170383", "name": "Cabbage, raw"},
    {"id": "169967", "name": "Leeks, (bulb and lower leaf-portion), raw"},
    {"id": "175194", "name": "Beans, navy, mature seeds, raw"},
    {"id": "175195", "name": "Beans, white, mature seeds, canned"},
    {"id": "174289", "name": "Beans, kidney, red, mature seeds, raw"},
    {"id": "172421", "name": "Lentils, raw"},
    {"id": "175237", "name": "Chickpeas (garbanzo beans, bengal gram), mature seeds, raw"},
    {"id": "169761", "name": "Wheat flour, white, all-purpose, unenriched"},
    {"id": "168897", "name": "Rice, white, long-grain, regular, unenriched, raw"},
    {"id": "170273", "name": "Pasta, dry, unenriched"},
    {"id": "168994", "name": "Granola, homemade"},
    {"id": "172336", "name": "Oil, olive, salad or cooking"},
    {"id": "171410", "name": "Oil, sunflower, linoleic, (approx. 65%)"},
    {"id": "171287", "name": "Egg, whole, raw, fresh"},
    {"id": "169640", "name": "Honey"},
    {"id": "169655", "name": "Sugars, granulated"},
    {"id": "170276", "name": "Sugar, powdered"},
    {"id": "171706", "name": "Apples, raw, with skin"},
    {"id": "167762", "name": "Blueberries, raw"},
    {"id": "167758", "name": "Strawberries, raw"},
    {"id": "174673", "name": "Blueberries, frozen, unsweetened"},
    {"id": "169910", "name": "Lemon juice, raw"},
    {"id": "169094", "name": "Olives, ripe, canned (small-extra large)"},
    {"id": "173440", "name": "Olives, pickled, canned or bottled, green"},
    {"id": "170926", "name": "Spices, pepper, black"},
    {"id": "171328", "name": "Spices, oregano, dried"},
    {"id": "171320", "name": "Spices, bay leaf"},
    {"id": "172231", "name": "Salt, table"},
    {"id": "172155", "name": "Vinegar, red wine"},
    {"id": "170581", "name": "Walnuts, English"},
    {"id": "170162", "name": "Almonds"},
    {"id": "170148", "name": "Sunflower seed kernels, dry roasted, without salt"},
    {"id": "174167", "name": "Water, tap, drinking"},
    {"id": "174834", "name": "Wine, table, red"},
    {"id": "169416", "name": "Margarine, regular, hard, soybean"},
    {"id": "171033", "name": "Baking powder"},
    {"id": "172185", "name": "Cream, fluid, heavy whipping"},
    {"id": "174176", "name": "Sauce, tomato, canned"},
    {"id": "170501", "name": "Mushrooms, white, raw"},
]


class USDASearchTool:
    """Keyword + Jaccard similarity search. Replace with FAISS in production."""

    def search(self, query: str, top_k: int = 10) -> list[USDACandidate]:
        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored: list[tuple[float, dict]] = []
        for entry in USDA_DATABASE:
            entry_tokens = set(re.findall(r"\w+", entry["name"].lower()))
            if not entry_tokens:
                continue
            overlap = len(query_tokens & entry_tokens)
            union = len(query_tokens | entry_tokens)
            score = overlap / union if union else 0.0
            # small boost for long shared tokens
            for t in query_tokens:
                if len(t) > 4 and t in entry["name"].lower():
                    score = min(1.0, score + 0.12)
            scored.append((round(score, 3), entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        seen, results = set(), []
        for score, entry in scored:
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            results.append(USDACandidate(usda_id=entry["id"], name=entry["name"], score=score))
            if len(results) >= top_k:
                break
        return results


# ---------------------------------------------------------------------------
# Macedonian → English vocabulary (rule-based fallback)
# ---------------------------------------------------------------------------

MK_DICT: dict[str, str] = {
    "павлака": "sour cream",
    "кисела павлака": "sour cream cultured",
    "сирење": "white cheese feta",
    "кромид": "onion raw",
    "лук": "garlic raw",
    "домат": "tomato raw",
    "домати": "tomatoes raw",
    "краставица": "cucumber raw",
    "пиперка": "pepper paprika spice",
    "суви пиперки": "peppers dried",
    "свежа пиперка": "peppers sweet raw",
    "зелена пиперка": "peppers sweet green raw",
    "црвена пиперка": "peppers sweet red raw",
    "лута пиперка": "peppers chili hot raw",
    "црвен пипер": "spices paprika red pepper",
    "масло": "oil olive cooking",
    "зејтин": "oil olive",
    "сончогледово масло": "oil sunflower",
    "путер": "butter salted",
    "маргарин": "margarine",
    "јајце": "egg whole raw",
    "јајца": "egg whole raw",
    "жолчки": "egg yolks",
    "белки": "egg whites",
    "брашно": "wheat flour white",
    "шеќер": "sugar granulated",
    "шеќер во прав": "sugar powdered",
    "ванилин шеќер": "sugar vanilla",
    "сол": "salt table",
    "сол по потреба": "salt table",
    "млеко": "milk whole",
    "кондензирано млеко": "milk condensed",
    "вода": "water",
    "вода по потреба": "water",
    "масло по потреба": "oil olive cooking",
    "грав": "beans navy white dried",
    "бел грав": "beans navy white",
    "леќа": "lentils raw",
    "наут": "chickpeas garbanzo",
    "ориз": "rice white",
    "тестенини": "pasta dry",
    "макарони": "pasta macaroni",
    "шпагети": "pasta spaghetti",
    "месо": "meat beef",
    "пилешко": "chicken breast raw",
    "пилешко месо": "chicken breast",
    "говедско": "beef ground raw",
    "говедско месо": "beef",
    "свинско": "pork fresh raw",
    "свинско месо": "pork",
    "јагнешко": "lamb ground raw",
    "јагнешко месо": "lamb",
    "риба": "fish",
    "шунка": "ham pork cured",
    "сланина": "bacon pork cured",
    "чадена сланина": "bacon pork smoked",
    "маст": "lard pork fat",
    "свинска маст": "lard",
    "суво месо": "pork cured dried",
    "маслинки": "olives ripe canned",
    "оцет": "vinegar red wine",
    "вински оцет": "vinegar red wine",
    "вино": "wine red",
    "бело вино": "wine white",
    "мед": "honey",
    "прашок за печење": "baking powder",
    "сода бикарбона": "baking soda",
    "цимет": "cinnamon spices",
    "оригано": "oregano dried spices",
    "нане": "mint herbs dried",
    "нане по потреба": "mint herbs",
    "магдонос": "parsley fresh",
    "копар": "dill fresh herbs",
    "ловоров лист": "bay leaf spices",
    "бибер": "pepper black spices",
    "ореви": "walnuts english",
    "бадеми": "almonds",
    "лешници": "hazelnuts",
    "сусам": "sesame seeds",
    "тиквини семки": "pumpkin seeds",
    "сончоглед": "sunflower seeds",
    "јаболка": "apples raw",
    "јаболко": "apple raw",
    "лимон": "lemon juice",
    "портокал": "orange raw",
    "малини": "raspberries",
    "јагоди": "strawberries raw",
    "боровинки": "blueberries raw",
    "грозје": "grapes raw",
    "банана": "bananas raw",
    "компир": "potatoes raw",
    "морков": "carrots raw",
    "спанаќ": "spinach raw",
    "зелка": "cabbage raw",
    "праз": "leeks raw",
    "печурки": "mushrooms white raw",
    "буковец": "mushrooms oyster",
    "шампињони": "mushrooms white raw",
    "тиквица": "zucchini squash raw",
    "патлиџан": "eggplant raw",
    "зеленчук": "vegetables mixed",
    "рикота": "ricotta cheese",
    "мозарела": "mozzarella cheese",
    "пармезан": "parmesan cheese",
    "горгонзола": "cheese blue gorgonzola",
    "кашкавал": "cheese yellow cheddar",
    "мешан сув зачин": "spices mixed herbs dried",
    "зачин": "spices herbs mixed",
    "суви зачини": "spices dried mixed",
    "бисквити": "cookies biscuits",
    "чоколадо": "chocolate dark",
    "какао": "cocoa powder",
    "желатин": "gelatin",
    "скроб": "starch cornstarch",
}

GENERIC_MK = {
    "павлака", "сирење", "месо", "пиперка", "масло", "млеко",
    "маст", "суво месо", "маслинки", "грав", "риба", "леќа",
}
GENERIC_EN = {
    "oil", "cheese", "meat", "cream", "pepper", "milk", "butter",
    "flour", "sugar", "salt", "beans", "nuts", "fish",
}


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class EntityLinkingAgent:

    def __init__(
        self,
        recipes_path: str,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
    ):
        key = openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self.client = None
        if key and _OPENAI_AVAILABLE:
            try:
                self.client = _OpenAI(api_key=key)
            except Exception:
                pass
        self.model = model
        self.recipe_tool = RecipeContextTool(recipes_path)
        self.usda_tool = USDASearchTool()

    def _llm(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self.client:
            print("DEBUG: No client available for LLM call", flush=True)
            return ""
        kwargs: dict = dict(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=800,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            print(f"DEBUG: Calling LLM with model {self.model}", flush=True)
            resp = self.client.chat.completions.create(**kwargs)
            result = resp.choices[0].message.content or ""
            print(f"DEBUG: LLM response received: {len(result)} chars", flush=True)
            return result
        except Exception as e:
            print(f"DEBUG: LLM error: {str(e)}", flush=True)
            return ""

    # ------------------------------------------------------------------
    # Stage 1
    # ------------------------------------------------------------------
    def _stage_analyze(self, ingredient: str) -> tuple[str, str]:
        raw = self._llm(
            "Detect language (BCP-47) and translate to English. "
            "Respond ONLY with JSON: {\"language\": \"mk\", \"english\": \"...\"}.",
            f"Ingredient: {ingredient}",
            json_mode=True,
        )
        if raw:
            try:
                p = json.loads(raw)
                return p.get("language", "mk"), p.get("english", ingredient)
            except Exception:
                pass

        # Fallback: Cyrillic detection + dictionary lookup
        has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in ingredient)
        if has_cyrillic:
            lower = ingredient.lower().strip()
            # 1. Exact match
            if lower in MK_DICT:
                return "mk", MK_DICT[lower]
            # 2. Longest-prefix match (handles "кромид по потреба" → кромид)
            best_key, best_val = "", ""
            for key, val in MK_DICT.items():
                if lower.startswith(key) and len(key) > len(best_key):
                    best_key, best_val = key, val
            if best_val:
                return "mk", best_val
            # 3. Substring match (ingredient contains dict key)
            for key, val in sorted(MK_DICT.items(), key=lambda x: -len(x[0])):
                if key in lower:
                    return "mk", val
            # 4. Token-level match
            tokens = lower.split()
            translations = []
            for tok in tokens:
                if tok in MK_DICT:
                    translations.append(MK_DICT[tok])
            if translations:
                return "mk", " ".join(translations)
            return "mk", ingredient  # untranslated, pass as-is
        return "en", ingredient

    # ------------------------------------------------------------------
    # Stage 2
    # ------------------------------------------------------------------
    def _stage_decide_context(self, ingredient: str, english: str) -> bool:
        raw = self._llm(
            "Is this ingredient ambiguous enough to need recipe context for USDA mapping? "
            "Respond ONLY with JSON: {\"needs_context\": true/false, \"reason\": \"...\"}.",
            f"Original: {ingredient}\nEnglish: {english}",
            json_mode=True,
        )
        if raw:
            try:
                return bool(json.loads(raw).get("needs_context", False))
            except Exception:
                pass

        tokens = set(ingredient.lower().split()) | set(english.lower().split())
        return bool(tokens & (GENERIC_MK | GENERIC_EN))

    # ------------------------------------------------------------------
    # Stage 4: query formulation
    # ------------------------------------------------------------------
    def _formulate_query(self, english: str, context: list[ContextRecipe]) -> str:
        if not context:
            return english
        ctx = "\n".join(f"- {c.title}: {c.usage_note}" for c in context[:3])
        raw = self._llm(
            "Given an ingredient and recipe context, write the best USDA FoodData Central search query. "
            "Respond ONLY with JSON: {\"query\": \"...\"}.",
            f"Ingredient: {english}\nContext:\n{ctx}",
            json_mode=True,
        )
        if raw:
            try:
                return json.loads(raw).get("query", english)
            except Exception:
                pass
        return english

    # ------------------------------------------------------------------
    # Stage 5: evaluate
    # ------------------------------------------------------------------
    def _stage_evaluate(
        self,
        ingredient_original: str,
        english: str,
        candidates: list[USDACandidate],
        context: list[ContextRecipe],
    ) -> tuple[Optional[USDACandidate], int, str, str]:
        if not candidates:
            return None, 0, "low", "No USDA candidates found."

        cand_text = "\n".join(
            f"{i+1}. [{c.usda_id}] {c.name} (score: {c.score})"
            for i, c in enumerate(candidates[:8])
        )
        ctx_text = (
            "\n".join(f"- {c.title}: {c.usage_note}" for c in context[:3])
            if context else "No context."
        )
        print(f"DEBUG: _stage_evaluate - client is: {self.client}", flush=True)
        raw = self._llm(
            "Select the best USDA entry. "
            "Respond ONLY with JSON: {\"selected_index\": 1, \"confidence\": 85, \"reasoning\": \"...\"}. "
            "selected_index is 1-based (0 = no match). confidence is 0–100.",
            f"Ingredient: {ingredient_original} / {english}\nContext:\n{ctx_text}\nCandidates:\n{cand_text}",
            json_mode=True,
        )
        print(f"DEBUG: _stage_evaluate - raw response length: {len(raw) if raw else 0}", flush=True)
        if raw:
            try:
                p = json.loads(raw)
                idx = int(p.get("selected_index", 1)) - 1
                conf = min(100, max(0, int(p.get("confidence", 70))))
                reason = p.get("reasoning", "")
                if 0 <= idx < len(candidates):
                    lv = "high" if conf >= 80 else "med" if conf >= 55 else "low"
                    return candidates[idx], conf, lv, reason
            except Exception:
                pass

        # Fallback: highest score
        best = max(candidates, key=lambda c: c.score)
        conf = int(min(100, best.score * 110))
        lv = "high" if conf >= 80 else "med" if conf >= 55 else "low"
        reason = (
            f"Rule-based selection: highest keyword similarity score ({best.score:.2f}). "
            f"Add an OpenAI API key for LLM-driven reasoning."
        )
        return best, conf, lv, reason

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def link(self, ingredient_name: str) -> AgentTrace:
        t0 = time.time()
        trace = AgentTrace(
            ingredient_original=ingredient_name,
            detected_language="",
            english_translation="",
        )

        lang, english = self._stage_analyze(ingredient_name)
        trace.detected_language = lang
        trace.english_translation = english
        trace.stages_completed.append("analyze")

        needs_ctx = self._stage_decide_context(ingredient_name, english)
        trace.is_ambiguous = needs_ctx
        trace.needs_context = needs_ctx
        trace.stages_completed.append("decide_context")

        context: list[ContextRecipe] = []
        if needs_ctx:
            context = self.recipe_tool.search(ingredient_name, top_k=5)
            trace.context_recipes = context
            trace.tool_calls.append(ToolCall(
                name="get_recipe_context",
                args={"ingredient": ingredient_name, "top_k": 5},
                result_summary=f"Found {len(context)} recipes with this ingredient",
            ))
        trace.stages_completed.append("fetch_context")

        query = self._formulate_query(english, context)
        trace.search_query = query

        candidates = self.usda_tool.search(query, top_k=10)
        trace.candidates = candidates
        trace.tool_calls.append(ToolCall(
            name="search_usda_classes",
            args={"query": query, "top_k": 10},
            result_summary=f"Found {len(candidates)} USDA candidates",
        ))
        trace.stages_completed.append("search_usda")

        best, conf, lv, reason = self._stage_evaluate(
            ingredient_name, english, candidates, context
        )
        if best:
            best.selected = True
            trace.selected_usda_id = best.usda_id
            trace.selected_usda_name = best.name
        trace.confidence = conf
        trace.confidence_level = lv
        trace.reasoning = reason
        trace.stages_completed.append("evaluate")

        trace.processing_time_ms = int((time.time() - t0) * 1000)
        return trace

    def link_recipe(self, recipe: dict) -> dict:
        results = []
        for ing in recipe.get("ingredients", []):
            name = ing.get("name", "").strip()
            if not name:
                continue
            results.append({"original": ing, "trace": self.link(name)})
        return {"recipe": recipe, "linked_ingredients": results}
