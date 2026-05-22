"""
Streamlit UI — Agentic Entity Linking Explorer
=====================================================
Визуелизира го целосниот reasoning процес на агентот:
  • Кои алатки ги повикал и зошто
  • Кои рецепти земал за контекст
  • Кандидати од USDA со scores
  • Финален избор + reasoning + confidence

Може да се стартува директно (без FastAPI):
    streamlit run ui/app.py

Или да го pointed кон FastAPI backend:
    API_URL=http://localhost:8000 streamlit run ui/app.py
"""

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — allow running from project root or ui/ dir
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Agentic Linking of Recipes",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "selected_tag_filter" not in st.session_state:
    st.session_state.selected_tag_filter = None
if "recipe_to_view" not in st.session_state:
    st.session_state.recipe_to_view = None

# ---------------------------------------------------------------------------
# Custom CSS — clean, academic aesthetic
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Typography & spacing */
.block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
hr { margin: 0.3rem 0 !important; }
h1 { font-size: 2.2rem !important; font-weight: 700 !important; margin: 0.5rem 0 !important; }
h2 { font-size: 1.6rem !important; font-weight: 700 !important; margin: 0.3rem 0 !important; }
h3 { font-size: 1.3rem !important; font-weight: 600 !important; margin: 0.2rem 0 !important; }
p { font-size: 1.05rem !important; }
.stMarkdown { font-size: 1.05rem !important; }
div { font-size: 1.05rem !important; }

/* Tag buttons styling */
.stButton > button {
    width: 100% !important;
    background-color: #be185d !important;
    color: white !important;
    border: none !important;
    padding: 8px 12px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    border-radius: 5px !important;
    height: auto !important;
}
.stButton > button:hover {
    background-color: #831843 !important;
}

/* Stage cards */
.stage-card {
    background: #f8f9fa;
    border-left: 4px solid #dee2e6;
    border-radius: 3px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.4rem;
    font-size: 1.02rem;
}
.stage-done  { border-left-color: #28a745; background: #f0faf3; }
.stage-skip  { border-left-color: #adb5bd; background: #f8f9fa; opacity: 0.7; }
.stage-active{ border-left-color: #007bff; background: #f0f4ff; }

/* Tool call block */
.tool-call {
    background: #1e1e2e;
    color: #cdd6f4;
    border-radius: 5px;
    padding: 0.5rem 0.75rem;
    font-family: monospace;
    font-size: 0.95rem;
    margin: 0.3rem 0;
}
.tool-name { color: #89b4fa; font-weight: 700; font-size: 0.98rem; }
.tool-result { color: #a6e3a1; font-size: 0.95rem; }

/* Ingredient chip */
.ing-chip {
    display: inline-block;
    background: #e9ecef;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 0.95rem;
    margin: 3px 3px 3px 0;
    cursor: default;
    font-weight: 500;
}

/* USDA badge */
.usda-badge {
    background: #d1f5d3;
    color: #155724;
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 0.9rem;
    font-family: monospace;
    font-weight: 600;
}

/* Confidence bar */
.conf-bar-outer {
    background: #dee2e6;
    border-radius: 4px;
    height: 8px;
    width: 100%;
}
.conf-bar-inner {
    border-radius: 4px;
    height: 8px;
    transition: width 0.4s ease;
}

/* Context recipe */
.ctx-recipe {
    background: #fff8e1;
    border-left: 4px solid #ffc107;
    border-radius: 3px;
    padding: 0.5rem 0.75rem;
    margin: 0.25rem 0;
    font-size: 0.98rem;
}

/* Candidate row */
.cand-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.5rem 0.7rem;
    border-radius: 4px;
    margin: 0.2rem 0;
    font-size: 1rem;
}
.cand-winner { background: #d4edda; }
.cand-normal { background: #f8f9fa; }
.cand-score {
    min-width: 50px;
    text-align: right;
    font-family: monospace;
    font-size: 0.95rem;
    color: #6c757d;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load agent & data (cached)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading dataset and agent …")
def load_agent_and_data():
    from agent.entity_linker import EntityLinkingAgent

    data_path = str(PROJECT_ROOT / "data" / "parsed_recipes.json")
    usda_csv = str(PROJECT_ROOT / "usdaClasses.csv")

    with open(data_path, encoding="utf-8") as f:
        recipes = json.load(f)

    agent = EntityLinkingAgent(
        recipes_path=data_path,
        usda_csv_path=usda_csv,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
    )
    return agent, recipes


# Lazy load agent and recipes to avoid ScriptRunContext errors
agent, recipes = load_agent_and_data()

# ---------------------------------------------------------------------------
# Sidebar — recipe search & selection
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🍳 Agentic Linker")
    st.caption("Macedonian Recipes → USDA FoodData Central")
    st.divider()

    st.subheader("📚 Select Recipe")
    search_query = st.text_input("Search by title or tags", placeholder="e.g. chicken, cake …")

    # Filter recipes
    if st.session_state.selected_tag_filter:
        # Filter by selected tag
        filtered = [
            (i, r) for i, r in enumerate(recipes)
            if st.session_state.selected_tag_filter in r.get("tags", [])
        ]
    elif search_query:
        ql = search_query.lower()
        filtered = [
            (i, r) for i, r in enumerate(recipes)
            if ql in r.get("title", "").lower()
            or any(ql in t.lower() for t in r.get("tags", []))
        ]
    else:
        import random as _rng
        _rng.seed(0)
        sample_idxs = _rng.sample(range(len(recipes)), min(80, len(recipes)))
        filtered = [(i, recipes[i]) for i in sorted(sample_idxs)]

    filtered = filtered[:60]  # cap display

    recipe_options = {f"{r['title']} (#{i})": i for i, r in filtered}

    if not recipe_options:
        st.warning("No recipes found matching your filter.")
        st.session_state.selected_tag_filter = None
        st.rerun()

    # Determine which recipe to select
    if st.session_state.recipe_to_view is not None:
        # Use the recipe that was requested to be viewed
        selected_idx = st.session_state.recipe_to_view
        st.session_state.recipe_to_view = None  # Clear it after using
        # Find the label for this recipe
        selected_label = None
        for label, idx in recipe_options.items():
            if idx == selected_idx:
                selected_label = label
                break
        if not selected_label and recipe_options:
            selected_label = list(recipe_options.keys())[0]
    else:
        # Get first option as default
        default_idx = 0 if recipe_options else None
        selected_label = st.selectbox(
            "Recipe",
            options=list(recipe_options.keys()),
            index=default_idx,
            label_visibility="collapsed",
        )
        selected_idx = recipe_options[selected_label]

    selected_recipe = recipes[selected_idx]

    st.divider()
    st.subheader("🔬 Test Single Ingredient")
    custom_ingredient = st.text_input("Ingredient (Macedonian or English)", placeholder="e.g. sour cream, onion …")
    run_single = st.button("⚡ Analyze", type="primary", use_container_width=True)

    st.divider()
    st.subheader("🔑 LLM Configuration")

    # --- Anthropic ---
    ant_key_input = st.text_input(
        "Anthropic API Key (preferred)",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="Claude Haiku is used for all reasoning steps.",
    )
    if ant_key_input and ant_key_input != os.environ.get("ANTHROPIC_API_KEY", ""):
        os.environ["ANTHROPIC_API_KEY"] = ant_key_input
        try:
            import anthropic as _ant
            client = _ant.Anthropic(api_key=ant_key_input)
            # Light validation — list models endpoint
            client.models.list()
            agent.client = client
            agent.provider = "anthropic"
            agent.model = "claude-haiku-4-5-20251001"
            st.sidebar.success("Anthropic connected — Claude Haiku active")
        except Exception as e:
            st.sidebar.error(f"Anthropic error: {e}")
            agent.client = None
            agent.provider = None

    # --- OpenAI fallback ---
    oai_key_input = st.text_input(
        "OpenAI API Key (fallback)",
        type="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
        help="Used only if no Anthropic key is set.",
    )
    if oai_key_input and oai_key_input != os.environ.get("OPENAI_API_KEY", "") and not agent.client:
        os.environ["OPENAI_API_KEY"] = oai_key_input
        try:
            from openai import OpenAI
            client = OpenAI(api_key=oai_key_input)
            client.models.list()
            agent.client = client
            agent.provider = "openai"
            agent.model = "gpt-3.5-turbo"
            st.sidebar.success("OpenAI connected — GPT-3.5 active")
        except Exception as e:
            st.sidebar.error(f"OpenAI error: {e}")
            agent.client = None
            agent.provider = None

    # Clear clients when keys are removed
    if not ant_key_input and not oai_key_input and agent.client:
        agent.client = None
        agent.provider = None
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    # Provider status badge
    if agent.provider == "anthropic":
        st.sidebar.success(f"LLM: Claude Haiku (Anthropic)")
    elif agent.provider == "openai":
        st.sidebar.info(f"LLM: GPT-3.5 (OpenAI)")
    else:
        st.sidebar.warning("LLM: rule-based fallback")

    st.divider()
    st.caption(f"📦 {len(recipes):,} Macedonian recipes")
    st.caption(f"🗄 {agent.usda_tool.size:,} USDA food entries")

# ---------------------------------------------------------------------------
# Helper: render a single agent trace
# ---------------------------------------------------------------------------

def render_confidence_bar(confidence: int, level: str):
    color = {"high": "#28a745", "med": "#ffc107", "low": "#dc3545"}.get(level, "#6c757d")
    label = {"high": "High", "med": "Medium", "low": "Low"}.get(level, level)
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin:4px 0">
      <div class="conf-bar-outer" style="flex:1">
        <div class="conf-bar-inner" style="width:{confidence}%;background:{color}"></div>
      </div>
      <span style="font-size:0.85rem;font-weight:600;color:{color}">{confidence}% — {label}</span>
    </div>
    """, unsafe_allow_html=True)


def render_trace(trace, idx: int = 0):
    with st.container():
        # Header
        col_a, col_b = st.columns([3, 1])
        with col_a:
            lang_flag = "🇲🇰" if trace.detected_language == "mk" else "🇬🇧"
            st.markdown(f"**{lang_flag} `{trace.ingredient_original}`**")
        with col_b:
            st.caption(f"⏱ {trace.processing_time_ms} ms")

        # Stage 1 — Analyze
        lang_label = {"mk": "Macedonian", "en": "English"}.get(trace.detected_language, trace.detected_language)
        st.markdown(f"""<div class="stage-card stage-done">
            <strong>① Analyze</strong> — Јазик: <code>{lang_label}</code>
            {"&nbsp;→ Превод: <code>" + trace.english_translation + "</code>" if trace.detected_language != "en" else ""}
        </div>""", unsafe_allow_html=True)

        # Stage 2 — Decide context
        if trace.needs_context:
            st.markdown(f"""<div class="stage-card stage-done">
                <strong>② Decide context</strong> — This ingredient is <em>ambiguous</em> — context is needed.
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="stage-card stage-skip">
                <strong>② Decide context</strong> — Clear ingredient — context is not needed.
            </div>""", unsafe_allow_html=True)

        # Stage 3 — Context recipes
        if trace.needs_context:
            ctx_html = "".join(
                f'<div class="ctx-recipe"><strong>{c.title}</strong><br><small>{c.usage_note}</small></div>'
                for c in trace.context_recipes
            ) or "<em>Нема рецепти пронајдени.</em>"
            tool_html = ""
            for tc in trace.tool_calls:
                if "recipe_context" in tc.name:
                    tool_html = f"""<div class="tool-call">
                        <span class="tool-name">{tc.name}</span>(<code style="color:#f9e2af">{json.dumps(tc.args, ensure_ascii=False)}</code>)<br>
                        <span class="tool-result">→ {tc.result_summary}</span>
                    </div>"""
            st.markdown(f"""<div class="stage-card stage-done">
                <strong>③ Fetch context</strong>{tool_html}
                {ctx_html}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="stage-card stage-skip">
                <strong>③ Fetch context</strong> — Skipped.
            </div>""", unsafe_allow_html=True)

        # Stage 4 — USDA Search
        usda_tool_html = ""
        for tc in trace.tool_calls:
            if "usda" in tc.name:
                usda_tool_html = f"""<div class="tool-call">
                    <span class="tool-name">{tc.name}</span>(<code style="color:#f9e2af">{json.dumps(tc.args, ensure_ascii=False)}</code>)<br>
                    <span class="tool-result">→ {tc.result_summary}</span>
                </div>"""

        cand_html = ""
        for c in trace.candidates[:8]:
            cls = "cand-winner" if c.selected else "cand-normal"
            star = " ✓" if c.selected else ""
            cand_html += f"""<div class="cand-row {cls}">
                <span class="cand-score">{int(c.score*100)}%</span>
                <span style="flex:1">{c.name}</span>
                <code style="font-size:0.75rem;color:#6c757d">{c.usda_id}{star}</code>
            </div>"""

        st.markdown(f"""<div class="stage-card stage-done">
            <strong>④ Search USDA</strong> — Query: <code>{trace.search_query}</code>
            {usda_tool_html}
            {cand_html}
        </div>""", unsafe_allow_html=True)

        # Stage 5 — Evaluate
        if trace.selected_usda_id:
            result_html = f"""<span class="usda-badge">USDA:{trace.selected_usda_id}</span>
            <strong> {trace.selected_usda_name}</strong>"""
        else:
            result_html = "<em>No matching USDA entity found.</em>"

        st.markdown(f"""<div class="stage-card stage-done">
            <strong>⑤ Evaluate & Select</strong><br>
            {result_html}
        </div>""", unsafe_allow_html=True)

        if trace.selected_usda_id:
            render_confidence_bar(trace.confidence, trace.confidence_level)

        if trace.reasoning:
            with st.expander("💬 Agent's Reasoning", expanded=False):
                st.info(trace.reasoning)


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

# Single ingredient mode
if run_single and custom_ingredient:
    st.title("🔬 Single Ingredient Analysis")
    st.markdown(f"**Ingredient:** `{custom_ingredient}`")

    with st.spinner("Agent is analyzing …"):
        trace = agent.link(custom_ingredient)

    render_trace(trace)
    st.stop()

# ---------------------------------------------------------------------------
# Recipe mode
# ---------------------------------------------------------------------------

st.write("")
st.write("")
st.title("🍳 Agentic Linking of Recipes")
st.caption("Link Macedonian ingredients to USDA FoodData Central")

# Recipe header
col1, col2 = st.columns([2, 1])
with col1:
    st.header(selected_recipe.get("title", "Unknown Recipe"))
    st.write("")  # Add spacing
    tags = selected_recipe.get("tags", [])[:8]

    # Create clickable tags with custom styling
    if tags:
        st.write("**Tags:**")
        # Create rows of tags (3 per row)
        for row_num, i in enumerate(range(0, len(tags), 3)):
            row_tags = tags[i:i+3]
            cols = st.columns(len(row_tags))
            for col_idx, tag in enumerate(row_tags):
                with cols[col_idx]:
                    if st.button(tag, key=f"tag_{row_num}_{col_idx}", use_container_width=True):
                        st.session_state.selected_tag_filter = tag
                        st.rerun()

    src = selected_recipe.get("source", "")
    if src:
        st.caption(f"[Source]({src})")

with col2:
    img = selected_recipe.get("image", "")
    if img:
        st.image(img, use_container_width=True)

# Show tag filter page if a tag is selected
if st.session_state.selected_tag_filter:
    st.title(f"Recipes with tag: {st.session_state.selected_tag_filter}")

    # Get all recipes with this tag
    matching_recipes = [(i, r) for i, r in enumerate(recipes) if st.session_state.selected_tag_filter in r.get("tags", [])]
    st.caption(f"Found {len(matching_recipes)} recipes")

    if st.button("← Back to Browse", key="back_btn"):
        st.session_state.selected_tag_filter = None
        st.rerun()

    st.divider()

    # Display recipes in a grid
    cols = st.columns(3, gap="medium")
    for idx, (recipe_idx, recipe) in enumerate(matching_recipes):
        col_idx = idx % 3
        with cols[col_idx]:
            st.subheader(recipe.get("title", "Unknown Recipe"))

            # Show image if available
            img = recipe.get("image", "")
            if img:
                st.image(img, use_container_width=True)

            # Show tags
            tags = recipe.get("tags", [])[:5]
            if tags:
                tag_text = " • ".join(tags)
                st.caption(f"Tags: {tag_text}")

            # Show ingredient count
            ing_count = len(recipe.get("ingredients", []))
            st.caption(f"📋 {ing_count} ingredients")

            # Click to view button
            if st.button("View Recipe", key=f"view_{recipe_idx}"):
                st.session_state.recipe_to_view = recipe_idx
                st.session_state.selected_tag_filter = None
                st.rerun()

    st.stop()

st.divider()

# Two columns: recipe details + linking results
left, right = st.columns([1, 1], gap="small")

with left:
    st.subheader("📋 Recipe")

    # Instructions
    instructions = selected_recipe.get("instructions", [])
    if instructions:
        with st.expander("📖 Instructions", expanded=False):
            for i, step in enumerate(instructions, 1):
                st.markdown(f"**{i}.** {step}")

    # Ingredients table
    st.markdown("**Ingredients:**")
    ings = selected_recipe.get("ingredients", [])
    if ings:
        ing_data = []
        for ing in ings:
            qty = f"{ing.get('quantity','')} {ing.get('unit','')}".strip()
            ing_data.append({"Quantity": qty, "Ingredient": ing.get("name", "")})
        st.table(ing_data)
    else:
        st.info("No ingredients in this recipe.")

with right:
    st.subheader("🤖 Agent Analysis")

    if not ings:
        st.warning("No ingredients to analyze.")
    else:
        run_all = st.button("▶ Analyze All Ingredients", type="primary", use_container_width=True)

        # Single ingredient picker
        ing_names = [ing.get("name", "") for ing in ings if ing.get("name")]
        selected_ing = st.selectbox("Or select a single ingredient:", ["— select —"] + ing_names)

        if selected_ing and selected_ing != "— select —":
            with st.spinner(f"Агентот го анализира „{selected_ing} …"):
                trace = agent.link(selected_ing)
            render_trace(trace)

        elif run_all:
            progress = st.progress(0, text="Analyzing ingredients …")
            traces = []
            for i, ing in enumerate(ings):
                name = ing.get("name", "").strip()
                if not name:
                    continue
                progress.progress((i + 1) / len(ings), text=f"„{name}" + "“ …")
                trace = agent.link(name)
                traces.append((ing, trace))
                time.sleep(0.05)  # small visual delay
            progress.empty()

            st.success(f"✅ Analyzed {len(traces)} ingredients")

            # Summary table
            summary_rows = []
            for ing, tr in traces:
                qty = f"{ing.get('quantity','')} {ing.get('unit','')}".strip()
                conf_emoji = {"high": "🟢", "med": "🟡", "low": "🔴"}.get(tr.confidence_level, "⚪")
                summary_rows.append({
                    "Ingredient": ing.get("name", ""),
                    "Quantity": qty,
                    "USDA Entity": tr.selected_usda_name or "—",
                    "ID": f"USDA:{tr.selected_usda_id}" if tr.selected_usda_id else "—",
                    "Confidence": f"{conf_emoji} {tr.confidence}%",
                })
            st.markdown("**Mapping Summary:**")
            st.dataframe(summary_rows, use_container_width=True)

            # Detailed traces
            st.markdown("---")
            st.markdown("**Detailed Reasoning Traces:**")
            for ing, tr in traces:
                with st.expander(f"🔎 {ing.get('name', '')} → {tr.selected_usda_name or 'no match'}"):
                    render_trace(tr)

# ---------------------------------------------------------------------------
# Footer stats
# ---------------------------------------------------------------------------
st.divider()
col_s1, col_s2, col_s3 = st.columns(3)
col_s1.metric("Total Recipes", f"{len(recipes):,}")
col_s2.metric("With Ingredients", f"{sum(1 for r in recipes if r.get('ingredients')):,}")
col_s3.metric("Ingredients in Recipe", len(ings))
