"""
Temporary AI Search test app

POST /ai/manga/search
Body: { "query": string, "limit": int (optional, default 20) }

Uses Google Gemini to extract likely titles, keywords, and genres from free-form text
(storylines, similar titles, descriptions, etc.), then queries MongoDB for matches.

Notes:
- Set GEMINI_API_KEY in the environment to enable Gemini. If not set, a heuristic fallback
  keyword extractor is used.
- This file is intentionally separate from the main app for testing. After validation,
  we can integrate the endpoint into main.py.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.collation import Collation

try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None  # Gemini optional for local testing

try:
    from fuzzywuzzy import fuzz
except Exception:
    fuzz = None

try:
    from synonyms import SYNONYMS
except Exception:
    SYNONYMS = {}


def get_mongo_client() -> MongoClient:
    uri = os.getenv(
        "MONGO_URI",
        # Reuse the same default as main.py for consistency
        "mongodb://darshak:DarshakVasoya1310%40@165.232.60.4:27017/admin?authSource=admin",
    )
    return MongoClient(uri)


db_client = get_mongo_client()
db = db_client["admin"]
collection = db["manhwa"]  # We refer to these as "manga" in the API wording


class AISearchRequest(BaseModel):
    query: str = Field(..., description="Free-form text: storyline, similar titles, description, etc.")
    limit: int = Field(20, ge=1, le=50)
    model: Optional[str] = Field(None, description="Override Gemini model name (e.g., gemini-1.5-flash)")


class AISearchResponse(BaseModel):
    total: int
    results: List[Dict[str, Any]]
    ai: Dict[str, Any]


ai_app = FastAPI(title="AI Manga Search (Test)")
ai_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _setup_gemini(model_name: Optional[str] = None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name or "gemini-1.5-flash")
        return model
    except Exception:
        return None


def _ai_extract(query: str, model_name: Optional[str] = None) -> Dict[str, Any]:
    """Ask Gemini to extract structured hints from free-form text.

    Expected JSON-only answer with:
    {
      "titles": ["..."],            # likely exact or near-exact series names
      "include_keywords": ["..."],  # important keywords to match in name/alt/description
      "exclude_keywords": ["..."],  # things to avoid
      "genres": ["..."]             # genre hints
    }
    """
    model = _setup_gemini(model_name)
    if model is None:
        # Gemini unavailable; return empty extraction and rely on heuristic fallback
        return {"titles": [], "include_keywords": [], "exclude_keywords": [], "genres": [], "source": "heuristic"}

    prompt = (
        "You are an assistant that helps find manga/manhwa titles from a database. "
        "User text can be storyline, similar titles, or descriptions. "
        "Return ONLY compact JSON with keys: titles, include_keywords, exclude_keywords, genres. "
        "Do not add any commentary. Max 8 items per list.\n\n"
        f"User text: {query}\n"
    )

    try:
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        # Attempt to locate JSON block
        m = re.search(r"\{[\s\S]*\}$", text)
        candidate = m.group(0) if m else text
        data = json.loads(candidate)
        data.setdefault("titles", [])
        data.setdefault("include_keywords", [])
        data.setdefault("exclude_keywords", [])
        data.setdefault("genres", [])
        data["source"] = "gemini"
        return data
    except Exception:
        # Fallback to heuristic
        return {"titles": [], "include_keywords": [], "exclude_keywords": [], "genres": [], "source": "heuristic"}


_STOPWORDS = set(
    "the a an of and or to in on at for from with about into over after before between under again further then once here there when where why how all any both each few more most other some such no nor not only own same so than too very can will just don should now like similar story manga manhwa comic series".split()
)


def _heuristic_tokens(text: str) -> List[str]:
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    toks = [t for t in tokens if t and t not in _STOPWORDS and len(t) > 2]
    return list(dict.fromkeys(toks))[:10]


def _expand_with_synonyms(words: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for w in words:
        if w in seen:
            continue
        out.append(w)
        seen.add(w)
        for k, vs in (SYNONYMS or {}).items():
            if w == k or w in vs:
                for v in [k] + vs:
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
    return out[:20]


def _build_query(extract: Dict[str, Any]) -> Dict[str, Any]:
    titles: List[str] = extract.get("titles", [])
    include_keywords: List[str] = extract.get("include_keywords", [])
    genres: List[str] = extract.get("genres", [])

    # Expand keywords with synonyms
    include_keywords = _expand_with_synonyms(include_keywords)

    or_conditions: List[Dict[str, Any]] = []

    # Title-focused regex matches (boost exact-ish names)
    for t in titles[:8]:
        try:
            rx = re.compile(re.escape(t), re.IGNORECASE)
            or_conditions.append({"name": {"$regex": rx}})
            or_conditions.append({"alternative": {"$regex": rx}})
        except re.error:
            continue

    # Keyword matches across name/alternative/description
    for kw in include_keywords[:12]:
        try:
            rx = re.compile(re.escape(kw), re.IGNORECASE)
            or_conditions.append({"name": {"$regex": rx}})
            or_conditions.append({"alternative": {"$regex": rx}})
            or_conditions.append({"description": {"$regex": rx}})
        except re.error:
            continue

    base: Dict[str, Any] = {}
    if genres:
        base["genres"] = {"$in": [g for g in genres if isinstance(g, str) and g.strip()]}

    if or_conditions:
        if base:
            return {"$and": [base, {"$or": or_conditions}]}
        return {"$or": or_conditions}
    # If nothing extracted, return base (possibly empty) to avoid scanning entire collection
    return base if base else {"name": {"$regex": re.compile(".")}}  # cheap safeguard


def _score_and_sort(docs: List[Dict[str, Any]], extract: Dict[str, Any]) -> List[Dict[str, Any]]:
    titles = [t.lower() for t in extract.get("titles", [])]
    keywords = [k.lower() for k in extract.get("include_keywords", [])]

    def score(doc: Dict[str, Any]) -> float:
        name = (doc.get("name") or "").lower()
        alt = (doc.get("alternative") or "").lower()
        desc = (doc.get("description") or "").lower()
        s = 0.0
        # exact-ish title boost
        for t in titles:
            if t and t in name:
                s += 50
            if t and t in alt:
                s += 30
        # keyword matches
        for k in keywords:
            if k in name:
                s += 10
            if k in alt:
                s += 6
            if k in desc:
                s += 4
        # fuzzy fallback if available
        if fuzz is not None and titles:
            for t in titles:
                try:
                    s = max(s, float(fuzz.partial_ratio(t, name)))
                except Exception:
                    pass
        # add rating as tiny tie-breaker
        try:
            s += float(doc.get("rating") or 0) / 10.0
        except Exception:
            pass
        return s

    docs.sort(key=score, reverse=True)
    return docs


@ai_app.post("/ai/manga/search", response_model=AISearchResponse)
def ai_manga_search(payload: AISearchRequest):
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    extract = _ai_extract(query, model_name=payload.model)
    if extract.get("source") == "heuristic" and not extract.get("include_keywords") and not extract.get("titles"):
        # Heuristic keywords from the user query if AI unavailable
        kws = _heuristic_tokens(query)
        extract["include_keywords"] = kws

    mongo_query = _build_query(extract)

    projection = {
        "name": 1,
        "alternative": 1,
        "cover_image": 1,
        "rating": 1,
        "last_chapter": 1,
        "description": 1,
        "genres": 1,
        "updated_at": 1,
        "url": 1,
        "_id": 0,
    }

    # Use collation for case-insensitive sorting by name as a fallback
    cursor = (
        collection
        .find(mongo_query, projection)
        .collation(Collation(locale='en', strength=2))
        .limit(max(50, payload.limit))  # pull a little more to allow re-ranking
    )

    docs = list(cursor)
    docs = _score_and_sort(docs, extract)[: payload.limit]

    return AISearchResponse(
        total=len(docs),
        results=docs,
        ai={
            "source": extract.get("source"),
            "titles": extract.get("titles", []),
            "include_keywords": extract.get("include_keywords", []),
            "genres": extract.get("genres", []),
        },
    )


if __name__ == "__main__":
    # Optional quick local run: uvicorn ai_search_test:ai_app --reload
    import uvicorn

    port = int(os.getenv("PORT", "8010"))
    uvicorn.run("ai_search_test:ai_app", host="127.0.0.1", port=port, reload=True)
