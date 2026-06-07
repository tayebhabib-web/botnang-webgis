from __future__ import annotations

import json
import os
import random
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder=str(PROJECT_DIR), static_url_path="")
CORS(app, resources={r"/chat": {"origins": "*"}, r"/health": {"origins": "*"}})

# Use a stable OpenAI API model by default.
# If an old/local value such as "gpt-5.5" is in .env and fails, change OPENAI_MODEL in .env to gpt-4.1-mini.
RAW_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
# Some local .env files may contain a ChatGPT product name instead of an API model name.
# Use a stable API model fallback so the bot returns an answer instead of failing silently.
OPENAI_MODEL = "gpt-4.1-mini" if RAW_OPENAI_MODEL.lower() in {"gpt-5.5", "gpt-5-5"} else RAW_OPENAI_MODEL
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "700"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

ALLOWED_KEYWORDS = {
    "botnang", "webgis", "gis", "qgis", "leaflet", "qgis2web", "dashboard", "map",
    "population", "housing", "building", "buildings", "residential", "density", "heatmap",
    "scenario", "baseline", "growth", "decline", "forecast", "prediction", "simulation",
    "simulated", "age", "migration", "birth", "death", "natural balance", "net migration",
    "formula", "method", "methodology", "limitation", "komunis", "alkis", "postgis",
    "postgresql", "database", "schema", "data source", "stuttgart", "allocation", "area",
    "botnang_bot", "pgadmin", "year", "historical", "future", "trend",
    "highest", "lowest", "most", "least", "leastest", "populated", "zoom", "highlight",
    # allow project year questions, including interpolated/simulated year requests
    "2007", "2010", "2015", "2020", "2021", "2022", "2023", "2024", "2025",
    "2026", "2027", "2028", "2029", "2030", "2035", "2040",

    # common short words / spelling mistakes accepted for user questions
    "pop", "pop end", "popend", "population end", "popelation", "poplation", "pupulation",
    "people", "forecast", "forcast", "future", "projection", "prediction", "simulate",
    "simulation", "simulated", "bilding", "bulding", "residental", "residentail",
    "scnario", "senario", "scenerio", "migartion", "migraton", "densety", "hetmap",
    "formla", "projet", "project", "botnag", "botnanag", "botang",
}

REJECT_MESSAGE = (
    "I can only answer questions related to the Botnang Population & Housing WebGIS project, "
    "including population, housing/buildings, scenarios, age structure, migration, heatmap, "
    "dashboard, methodology, data sources, PostgreSQL/PostGIS, and limitations."
)

SYSTEM_PROMPT = """
You are BotnangBot, the live AI assistant for the project:
AI-Assisted Botnang Population & Housing WebGIS.

You must answer only from the provided Botnang WebGIS project context.

Rules:
1. Do not answer unrelated questions.
2. If a value is observed, say it is observed.
3. If a value is simulated, say it is simulated and not an official prediction.
4. Use project-specific values from PostgreSQL/context when available.
5. Be concise, natural, friendly, and presentation-friendly.
6. Do not use LaTeX, raw Markdown tables, or code-style blocks unless the user asks.
7. Write formulas in simple plain text.
8. If a requested exact value is not available, say so clearly.
""".strip()

# Final scenario rates used in the WebGIS/dashboard
POP_2025 = 12669
SCENARIO_RATES = {
    "baseline": -0.0006997557857302149,
    "growth": 0.008048173595038796,
    "decline": -0.009447685166499227,
}
OBSERVED_POP = {
    2007: 12838,
    2010: 12696,
    2015: 13062,
    2020: 13108,
    2025: 12669,
}

# Used only for the “least populated building” query to avoid tiny sliver polygons.
MIN_REALISTIC_BUILDING_AREA_M2 = 20


def scenario_population(year: int, scenario: str = "baseline") -> int:
    if year in OBSERVED_POP:
        return OBSERVED_POP[year]
    rate = SCENARIO_RATES.get(scenario, SCENARIO_RATES["baseline"])
    return round(POP_2025 * ((1 + rate) ** (year - 2025)))


def db_config() -> dict[str, str]:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME", "botnang_gis"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def get_db_connection():
    return psycopg2.connect(**db_config())


def normalize(text: str) -> str:
    """Basic cleanup: lowercase and remove extra spaces."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def normalize_question(text: str) -> str:
    """
    Cleans user questions and fixes common spelling mistakes.
    Example: popelation -> population, bilding -> building, scnario -> scenario.
    """
    cleaned = normalize(text)

    replacements = {
        "popelation": "population",
        "poplation": "population",
        "pupulation": "population",
        "pop end": "population end",
        "popend": "population end",
        "pop": "population",
        "bilding": "building",
        "bulding": "building",
        "residental": "residential",
        "residentail": "residential",
        "scnario": "scenario",
        "senario": "scenario",
        "scenerio": "scenario",
        "migartion": "migration",
        "migraton": "migration",
        "densety": "density",
        "hetmap": "heatmap",
        "formla": "formula",
        "forcast": "forecast",
        "projet": "project",
        "botnag": "botnang",
        "botnanag": "botnang",
        "botang": "botnang",
        "leastest": "least",
    }

    for wrong, correct in replacements.items():
        cleaned = re.sub(r"\b" + re.escape(wrong) + r"\b", correct, cleaned)

    return normalize(cleaned)


def similarity(a: str, b: str) -> float:
    """Returns how similar two words are, from 0 to 1."""
    return SequenceMatcher(None, a, b).ratio()


def is_project_related(question: str, history: list[dict[str, str]] | None = None) -> bool:
    """
    Checks whether a question is related to the Botnang WebGIS project.
    This version understands common spelling mistakes and similar words.
    """
    combined = question + " " + " ".join(str(m.get("content", "")) for m in (history or [])[-4:])
    text = normalize_question(combined)

    # 1) Exact or partial keyword match after spelling normalization.
    for keyword in ALLOWED_KEYWORDS:
        if normalize_question(keyword) in text:
            return True

    # 2) Fuzzy matching for spelling mistakes.
    words = re.findall(r"[a-zA-Z0-9_]+", text)
    normalized_keywords = [normalize_question(k) for k in ALLOWED_KEYWORDS]

    for word in words:
        if len(word) < 4:
            continue
        for keyword in normalized_keywords:
            if len(keyword) < 4:
                continue
            if similarity(word, keyword) >= 0.78:
                return True

    return False


def fetch_table(cur, label: str, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        return [{"context_error": str(exc), "context_label": label}]


def get_relevant_year(question: str) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", question)
    return int(match.group(1)) if match else None


def get_relevant_scenario(question: str) -> str:
    text = normalize(question)
    for scenario in ("growth", "decline", "baseline"):
        if scenario in text:
            return scenario
    return "baseline"


def build_calculated_context(question: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    requested_year = get_relevant_year(question)
    requested_scenario = get_relevant_scenario(question)
    years = [2007, 2010, 2015, 2020, 2025, 2030, 2035, 2040]
    if requested_year and requested_year not in years and 2007 <= requested_year <= 2040:
        years.append(requested_year)
        years = sorted(years)

    values = []
    for scenario in ("baseline", "growth", "decline"):
        for y in years:
            values.append({
                "year": y,
                "scenario": scenario,
                "population": scenario_population(y, scenario),
                "type": "observed KOMUNIS value" if y in OBSERVED_POP else "simulated scenario value"
            })

    return {
        "frontend_state": state or {},
        "requested_year": requested_year,
        "requested_scenario": requested_scenario,
        "scenario_rates": {
            "baseline": SCENARIO_RATES["baseline"],
            "growth": SCENARIO_RATES["growth"],
            "decline": SCENARIO_RATES["decline"],
            "note": "Baseline is average annual historical growth; Growth is average + standard deviation; Decline is average - standard deviation."
        },
        "calculated_population_values": values,
        "important_formula": "Future Population = Population_2025 × (1 + scenario rate)^(year - 2025)",
        "important_note": "Values after 2025 are simulated scenario values, not official forecasts."
    }


def get_project_context_from_postgres(question: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    year = get_relevant_year(question)
    scenario = get_relevant_scenario(question)

    context: dict[str, Any] = {
        "source": "PostgreSQL schema botnang_bot plus formula fallback from WebGIS code",
        "calculated_context": build_calculated_context(question, state),
        "tables_used": [
            "botnang_bot.project_context",
            "botnang_bot.latest_population",
            "botnang_bot.population_allocation_summary",
            "botnang_bot.building_type_summary",
            "botnang_bot.ai_building_category_summary",
            "botnang_bot.yearly_population_summary",
            "botnang_bot.population_forecast_summary",
            "botnang_bot.age_structure_summary",
            "botnang_bot.migration_balance_summary",
            "botnang_bot.all_year_context",
        ],
    }

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            context["project_context"] = fetch_table(
                cur, "project_context",
                "SELECT topic, content FROM botnang_bot.project_context ORDER BY topic;"
            )
            context["latest_population"] = fetch_table(
                cur, "latest_population",
                "SELECT * FROM botnang_bot.latest_population;"
            )
            context["population_allocation_summary"] = fetch_table(
                cur, "population_allocation_summary",
                "SELECT * FROM botnang_bot.population_allocation_summary;"
            )
            context["building_type_summary"] = fetch_table(
                cur, "building_type_summary",
                "SELECT * FROM botnang_bot.building_type_summary;"
            )
            context["ai_building_category_summary"] = fetch_table(
                cur, "ai_building_category_summary",
                "SELECT * FROM botnang_bot.ai_building_category_summary;"
            )
            context["population_forecast_summary"] = fetch_table(
                cur, "population_forecast_summary",
                """
                SELECT *
                FROM botnang_bot.population_forecast_summary
                WHERE year <= 2040
                ORDER BY year, scenario;
                """
            )
            context["yearly_population_summary"] = fetch_table(
                cur, "yearly_population_summary",
                """
                SELECT *
                FROM botnang_bot.yearly_population_summary
                ORDER BY year;
                """
            )
            context["age_structure_summary"] = fetch_table(
                cur, "age_structure_summary",
                "SELECT * FROM botnang_bot.age_structure_summary ORDER BY year;"
            )
            context["migration_balance_summary"] = fetch_table(
                cur, "migration_balance_summary",
                "SELECT * FROM botnang_bot.migration_balance_summary ORDER BY year;"
            )
            if year is not None:
                context["requested_year_context"] = fetch_table(
                    cur, "requested_year_context",
                    """
                    SELECT *
                    FROM botnang_bot.all_year_context
                    WHERE context_year = %s
                      AND (scenario IS NULL OR scenario = %s)
                    ORDER BY source_table, scenario;
                    """,
                    (year, scenario)
                )
            context["chat_history_storage"] = fetch_table(
                cur, "chat_history_storage",
                "SELECT COUNT(*) AS stored_interactions FROM botnang_bot.chat_history;"
            )

    return context


def save_chat_history(question: str, answer: str, related: bool, source_used: str, model_used: str) -> None:
    """Save chat history. Works with both simple and extended chat_history table structures."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO botnang_bot.chat_history
                        (question, answer, is_project_related, source_used, model_used)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (question, answer, related, source_used, model_used),
                    )
                except Exception:
                    conn.rollback()
                    cur.execute(
                        """
                        INSERT INTO botnang_bot.chat_history (question, answer)
                        VALUES (%s, %s);
                        """,
                        (question, answer),
                    )
            conn.commit()
    except Exception as exc:
        print(f"[BotnangBot] Could not save chat_history: {exc}")



def extract_requested_building_id(question: str) -> int | None:
    """
    Detect a building number/ID request and return the requested ID.

    Accepted examples:
    - show me building ID 100
    - zoom to building number 100
    - building 100
    - find house no 100
    - show me number 100
    - ID 100

    To avoid confusing population years with building IDs, plain years like 2025/2030
    are not treated as building IDs unless the word building/house/polygon is present.
    """
    q = normalize_question(question)

    # Strong patterns: clear building/house/polygon wording.
    strong_patterns = [
        r"\b(?:building|house|polygon)\s*(?:id|number|no\.?|#)?\s*(\d{1,6})\b",
        r"\b(?:residential\s+building|residential\s+polygon)\s*(?:id|number|no\.?|#)?\s*(\d{1,6})\b",
        r"\b(?:id|number|no\.?|#)\s*(\d{1,6})\s*(?:building|house|polygon)\b",
        r"\bnumber\s+of\s+(?:the\s+)?(?:building|house|polygon)\s*(\d{1,6})\b",
    ]
    for pattern in strong_patterns:
        match = re.search(pattern, q)
        if match:
            return int(match.group(1))

    # Medium pattern: user says ID/number with a map action. Useful for short chat prompts.
    # Example: "show me number 100" or "zoom to id 56".
    has_map_action = any(word in q for word in ("show", "zoom", "find", "go", "open", "select", "highlight", "where"))
    match = re.search(r"\b(?:id|number|no\.?|#)\s*(\d{1,6})\b", q)
    if has_map_action and match:
        candidate = int(match.group(1))
        if candidate not in OBSERVED_POP:  # avoid treating 2025, 2030 etc. as building IDs
            return candidate

    # Very short prompt: allow only a plain number in a realistic building ID range.
    # Your current residential building IDs are roughly 1-2197.
    if re.fullmatch(r"\d{1,4}", q):
        candidate = int(q)
        if 1 <= candidate <= 3000 and candidate not in OBSERVED_POP:
            return candidate

    return None

def get_specific_building_response(question: str) -> dict[str, Any] | None:
    """
    Returns a direct BotnangBot answer plus GeoJSON geometry when the user asks
    for a specific building ID, for example: 'show me building ID 100'.
    """
    requested_id = extract_requested_building_id(question)
    if requested_id is None:
        return None

    source_used = "PostgreSQL view public.botnang_building_population_2025"

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    "Area_m2" AS area_m2,
                    population_estimated,
                    geometry_geojson
                FROM public.botnang_building_population_2025
                WHERE id = %s
                  AND geometry_geojson IS NOT NULL
                LIMIT 1;
                """,
                (requested_id,),
            )
            row = cur.fetchone()

    if not row:
        return {
            "answer": f"I could not find building ID {requested_id} in the Botnang residential building population view. Please check whether this ID exists in the residential_candidate_buildings table.",
            "source_used": source_used,
        }

    building_id = row["id"]
    area_m2 = float(row["area_m2"] or 0)
    population_estimated = float(row["population_estimated"] or 0)
    geometry = json.loads(row["geometry_geojson"])

    specific_answers = [
        f"I found building ID {building_id}. Its footprint area is {area_m2:.2f} m², and the area-based model gives it about {population_estimated:.2f} estimated residents. I zoomed to it on the map.",
        f"Building ID {building_id} is available in the residential dataset. It has an area of {area_m2:.2f} m² and approximately {population_estimated:.2f} estimated people. I highlighted the building for you.",
        f"Here is building ID {building_id}: area {area_m2:.2f} m², estimated population {population_estimated:.2f} people. This is model-based, not household registration data, and the map is now zoomed to it.",
        f"Yes, building ID {building_id} exists. Based on its footprint area of {area_m2:.2f} m², the estimated population is around {population_estimated:.2f} residents. I selected it on the map."
    ]

    return {
        "answer": random.choice(specific_answers),
        "zoom_to": {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": building_id,
                "area_m2": area_m2,
                "population_estimated": population_estimated,
                "population_label": "selected_building",
                "popup_title": "Selected residential building",
                "min_area_filter_m2": None,
            },
        },
        "source_used": source_used,
    }



def get_extreme_building_response(question: str) -> dict[str, Any] | None:
    """
    Returns a direct BotnangBot answer plus GeoJSON geometry for Leaflet zoom
    when the user asks for the most/least populated estimated residential building.
    Uses the clean PostgreSQL view created in pgAdmin:
    public.botnang_building_population_2025
    """
    q = normalize_question(question)

    wants_most = any(phrase in q for phrase in (
        "most populated", "highest estimated population", "highest population",
        "most population", "maximum population", "biggest population",
        "zoom to the most", "show me the most"
    ))
    wants_least = any(phrase in q for phrase in (
        "least populated", "lowest estimated population", "lowest realistic estimated population",
        "realistic estimated population", "lowest population", "least population",
        "minimum population", "smallest population", "zoom to the least", "show me the least"
    )) or (
        ("lowest" in q or "least" in q or "minimum" in q or "smallest" in q)
        and ("building" in q or "residential" in q or "house" in q or "realistic" in q)
        and ("population" in q or "populated" in q)
    )

    if not (wants_most or wants_least):
        return None

    order_direction = "ASC" if wants_least else "DESC"
    label = "lowest realistic" if wants_least else "highest"
    area_filter_sql = f'AND "Area_m2" >= {MIN_REALISTIC_BUILDING_AREA_M2}' if wants_least else 'AND "Area_m2" > 0'
    source_used = "PostgreSQL view public.botnang_building_population_2025"

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    id,
                    "Area_m2" AS area_m2,
                    population_estimated,
                    geometry_geojson
                FROM public.botnang_building_population_2025
                WHERE population_estimated IS NOT NULL
                  {area_filter_sql}
                  AND geometry_geojson IS NOT NULL
                ORDER BY population_estimated {order_direction}
                LIMIT 1;
            """)
            row = cur.fetchone()

    if not row:
        return {
            "answer": "I could not find a residential building polygon with estimated population in the current Botnang database view.",
            "source_used": source_used,
        }

    building_id = row["id"]
    area_m2 = float(row["area_m2"] or 0)
    population_estimated = float(row["population_estimated"] or 0)
    geometry = json.loads(row["geometry_geojson"])

    if wants_least:
        least_answers = [
            f"I found the lowest realistic estimated population building: ID {building_id}. It has about {population_estimated:.2f} estimated residents and an area of {area_m2:.2f} m². I used the 20 m² filter so tiny sliver polygons are not selected, and I zoomed to it on the map.",
            f"After excluding very small polygons below 20 m², the lowest estimated residential building is ID {building_id}. Its estimated population is around {population_estimated:.2f} people, based on a footprint area of {area_m2:.2f} m². I highlighted it for you.",
            f"The smallest realistic estimated residential population is building ID {building_id}. It has approximately {population_estimated:.2f} estimated people and a building area of {area_m2:.2f} m². This is model-based, not household registration data, and the map is zoomed to it now.",
            f"Here is the lowest realistic case in the building-level model: building ID {building_id}, about {population_estimated:.2f} estimated residents. Its area is {area_m2:.2f} m². I applied the 20 m² minimum-area rule to avoid geometry slivers.",
            f"For the least populated realistic residential polygon, I selected building ID {building_id}. It has roughly {population_estimated:.2f} estimated residents from an area of {area_m2:.2f} m², and I have highlighted the location on the map."
        ]
        answer = random.choice(least_answers)
    else:
        most_answers = [
            f"I found the building with the highest estimated population: ID {building_id}. It has about {population_estimated:.2f} estimated residents and an area of {area_m2:.2f} m². I have highlighted it on the map.",
            f"The highest estimated population is located in building ID {building_id}. Based on the area-based allocation model, it has approximately {population_estimated:.2f} estimated residents. Its footprint area is {area_m2:.2f} m², and I zoomed to it for you.",
            f"Building ID {building_id} has the highest estimated population in the residential dataset. The estimated value is around {population_estimated:.2f} people, calculated from a building area of {area_m2:.2f} m².",
            f"Here is the largest estimated residential population in the model: building ID {building_id}, with about {population_estimated:.2f} estimated people. I have zoomed to the building and highlighted it on the map.",
            f"For the highest population estimate, the model selects building ID {building_id}. Its area is {area_m2:.2f} m² and the allocated population is about {population_estimated:.2f} people. This is an area-based estimate, not exact household data."
        ]
        answer = random.choice(most_answers)

    return {
        "answer": answer,
        "zoom_to": {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": building_id,
                "area_m2": area_m2,
                "population_estimated": population_estimated,
                "population_label": "lowest_realistic" if wants_least else "highest",
                "min_area_filter_m2": MIN_REALISTIC_BUILDING_AREA_M2 if wants_least else None,
            },
        },
        "source_used": source_used,
    }


@app.get("/normalize-test")
def normalize_test():
    raw_question = request.args.get("q", "")
    normalized = normalize_question(raw_question)
    return jsonify({
        "original": raw_question,
        "normalized": normalized,
        "is_project_related": is_project_related(raw_question)
    })


@app.get("/health")
def health():
    db_ok = False
    db_error = None
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                db_ok = True
    except Exception as exc:
        db_error = str(exc)

    return jsonify({
        "ok": True,
        "model": OPENAI_MODEL,
        "has_api_key": bool(os.getenv("OPENAI_API_KEY")),
        "database": os.getenv("DB_NAME", "botnang_gis"),
        "db_ok": db_ok,
        "db_error": db_error,
        "message": "BotnangBot backend is running."
    })


@app.get("/")
def index():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    original_question = str(data.get("question", "")).strip()
    question = normalize_question(original_question)
    history = data.get("history") or []
    state = data.get("state") or {}

    if not question:
        return jsonify({"answer": "Please write a question about the Botnang WebGIS project."}), 400

    requested_building_id = extract_requested_building_id(original_question)
    related = is_project_related(question, history) or requested_building_id is not None
    if not related:
        answer = REJECT_MESSAGE
        save_chat_history(original_question, answer, False, "rejected: outside Botnang WebGIS project scope", OPENAI_MODEL)
        return jsonify({"answer": answer})

    # Direct database answer for a specific building ID/number, for example:
    # "show me building ID 100", "zoom to building number 100", or even just "100".
    # This also returns GeoJSON geometry so the Leaflet frontend can zoom to the selected building.
    try:
        direct_building_response = get_specific_building_response(question)
        if direct_building_response is not None:
            answer = direct_building_response.get("answer", "")
            save_chat_history(
                original_question,
                answer,
                True,
                direct_building_response.get("source_used", "PostgreSQL building population view"),
                "direct PostgreSQL query"
            )
            return jsonify({k: v for k, v in direct_building_response.items() if k != "source_used"})
    except Exception as exc:
        answer = (
            "I tried to find that building ID, but the database view "
            "public.botnang_building_population_2025 could not be queried. Please check that the view exists. "
            "Technical detail: " + str(exc)
        )
        save_chat_history(original_question, answer, True, f"Specific building zoom query error: {exc}", "direct PostgreSQL query")
        return jsonify({"answer": answer, "error": str(exc)}), 500

    # Direct database answer for most/least populated estimated building.
    # This also returns GeoJSON geometry so the Leaflet frontend can zoom to the selected building.
    try:
        direct_building_response = get_extreme_building_response(question)
        if direct_building_response is not None:
            answer = direct_building_response.get("answer", "")
            save_chat_history(
                original_question,
                answer,
                True,
                direct_building_response.get("source_used", "PostgreSQL building population view"),
                "direct PostgreSQL query"
            )
            return jsonify({k: v for k, v in direct_building_response.items() if k != "source_used"})
    except Exception as exc:
        answer = (
            "I tried to find the most/least populated residential building, but the database view "
            "public.botnang_building_population_2025 could not be queried. Please check that the view exists. "
            "Technical detail: " + str(exc)
        )
        save_chat_history(original_question, answer, True, f"Building zoom query error: {exc}", "direct PostgreSQL query")
        return jsonify({"answer": answer, "error": str(exc)}), 500

    if client is None:
        answer = "BotnangBot backend is running, but OPENAI_API_KEY is missing. Add it in backend/.env, then restart server.py."
        save_chat_history(original_question, answer, True, "backend error: missing OpenAI API key", OPENAI_MODEL)
        return jsonify({"answer": answer}), 500

    try:
        pg_context = get_project_context_from_postgres(question, state)
    except Exception as exc:
        answer = (
            "BotnangBot could not connect to PostgreSQL. Please check DB_HOST, DB_PORT, "
            "DB_NAME, DB_USER, and DB_PASSWORD in backend/.env."
        )
        save_chat_history(original_question, answer, True, f"PostgreSQL connection error: {exc}", OPENAI_MODEL)
        return jsonify({"answer": answer, "error": str(exc)}), 500

    user_input = (
        "POSTGRESQL PROJECT CONTEXT AND CALCULATED WEBGIS CONTEXT:\n"
        f"{json.dumps(pg_context, ensure_ascii=False, default=str, indent=2)}\n\n"
        f"ORIGINAL USER QUESTION:\n{original_question}\n\n"
        f"NORMALIZED USER QUESTION:\n{question}"
    )

    try:
        # First try Responses API.
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_input,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        answer = (getattr(response, "output_text", "") or "").strip()

        # Fallback if output_text is empty for any reason.
        if not answer and hasattr(client, "chat"):
            chat_response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            answer = chat_response.choices[0].message.content.strip()

        if not answer:
            answer = "I could not generate an answer from the available Botnang project context."

        save_chat_history(
            question,
            answer,
            True,
            "PostgreSQL botnang_bot schema + calculated WebGIS scenario context",
            OPENAI_MODEL
        )
        return jsonify({"answer": answer})

    except Exception as exc:
        answer = (
            "BotnangBot could not contact the OpenAI API. Check OPENAI_MODEL and OPENAI_API_KEY "
            "in backend/.env, then restart server.py. Technical detail: " + str(exc)
        )
        save_chat_history(original_question, answer, True, f"OpenAI API error: {exc}", OPENAI_MODEL)
        return jsonify({"answer": answer, "error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
