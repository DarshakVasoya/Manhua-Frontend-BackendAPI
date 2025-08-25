
from fuzzywuzzy import fuzz
from synonyms import SYNONYMS
# Find chapter images by chapternum match

# ...existing code...


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from typing import List, Optional
import os
from urllib.parse import unquote

def get_mongo_client():
    uri = os.getenv("MONGO_URI", "mongodb://darshak:DarshakVasoya1310%40@165.232.60.4:27017/admin?authSource=admin")
    return MongoClient(uri)

app = FastAPI()

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://manhwagalaxy.org", "http://165.232.60.4:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection (admin database)
client = get_mongo_client()
db = client["admin"]
collection = db["manhwa"]

# Helper function to serialize MongoDB documents
def serialize_manhwa(manhwa):
    return {
        "id": str(manhwa["_id"]),
        "cover_image": manhwa.get("cover_image"),
        "name": manhwa.get("name"),
        "rating": manhwa.get("rating"),
        "last_chapter": manhwa.get("last_chapter"),
        "description": manhwa.get("description"),
        "alternative": manhwa.get("alternative"),
        "status": manhwa.get("status"),
        "type": manhwa.get("type"),
        "released": manhwa.get("released"),
        "author": manhwa.get("author"),
        "posted_on": manhwa.get("posted_on"),
        "views": manhwa.get("views"),
        "genres": manhwa.get("genres", []),
        "url": manhwa.get("url"),
        "chapters": manhwa.get("chapters", [])
    }

import re
import redis

# Redis connection (default settings, adjust as needed)
redis_client = redis.Redis(host='localhost', port=6379, db=0)
def normalize_name(name: str) -> str:
    # Remove non-alphanumeric, lowercase
    name = unquote(name)
    name = re.sub(r'[^A-Za-z0-9]', '', name)
    return name.lower()

@app.get("/manhwa")
def get_manhwa_list(genre: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None, page: int = 1, limit: int = 20):
    query = {}
    if genre:
        query["genres"] = genre
    if type:
        query["type"] = type
    if status:
        query["status"] = status
    skip = (page - 1) * limit
    projection = {"name": 1, "last_chapter": 1, "rating": 1, "cover_image": 1, "posted_on": 1, "updated_at": 1, "_id": 0}

    # Create a cache key based on query params
    cache_key = f"manhwa_home:{genre}:{type}:{status}:{page}:{limit}"
    cached = redis_client.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    # Sort descending by updated_at (newest first)
    manhwa_cursor = collection.find(query, projection).sort("updated_at", -1).skip(skip).limit(limit)
    total = collection.count_documents(query)
    import json
    def convert(obj):
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        else:
            return obj

    result = {
        "total": total,
        "page": page,
        "limit": limit,
        "results": convert(list(manhwa_cursor))
    }
    # Cache for 6 hours (21600 seconds)
    redis_client.setex(cache_key, 3600, json.dumps(result))
    return result

@app.get("/manhwa/search")
def search_manhwa(query: str, page: int = 1, limit: int = 20):
    query_str = normalize_name(query)
    skip = (page - 1) * limit
    projection = {"name": 1, "last_chapter": 1, "rating": 1, "cover_image": 1, "posted_on": 1, "updated_at": 1, "_id": 0}

    # Expand query with synonyms
    search_terms = [query_str]
    for key, values in SYNONYMS.items():
        if query_str == key or query_str in values:
            search_terms.extend([key] + values)

    # Fetch all candidates (limit for performance)
    candidates = list(collection.find({}, projection))
    # Fuzzy match
    matched = []
    for doc in candidates:
        name = doc.get("name", "").lower()
        for term in search_terms:
            score = fuzz.partial_ratio(term, name)
            if score >= 80:
                matched.append(doc)
                break

    # Pagination
    total = len(matched)
    results = matched[skip:skip+limit]
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "query": query,
        "results": results
    }

@app.get("/manhwa/{name}")
def get_manhwa_detail_by_name(name: str):
    import re
    # Normalize input: remove non-alphanumeric, lowercase
    def normalize(s):
        s = unquote(s)
        s = re.sub(r'[^A-Za-z0-9]', '', s)
        return s.lower()

    normalized_input = normalize(name)
    manhwa = None
    for doc in collection.find({}, {"name": 1, "_id": 1}):
        if "name" in doc and normalize(doc["name"]) == normalized_input:
            manhwa = collection.find_one({"_id": doc["_id"]})
            break
    if not manhwa:
        raise HTTPException(status_code=404, detail="Manhwa not found")
    data = serialize_manhwa(manhwa)
    data.pop("chapters", None)
    return data

@app.get("/manhwa/{name}/chapters")
def get_chapters(name: str, order: str = "desc"):
    normalized_input = normalize_name(name)
    manhwa = None
    for doc in collection.find({}, {"name": 1, "_id": 1}):
        if "name" in doc and normalize_name(doc["name"]) == normalized_input:
            manhwa = collection.find_one({"_id": doc["_id"]})
            break
    if not manhwa:
        raise HTTPException(status_code=404, detail="Manhwa not found")
    chapters = manhwa.get("chapters", [])
    # Exclude images from each chapter
    for chapter in chapters:
        chapter.pop("images", None)
    # Allow order param: desc (default) or asc
    if order == "desc":
        chapters = list(reversed(chapters))
    return chapters

@app.get("/manhwa/{name}/chapters/{chapter_number}")
def get_chapter_detail(name: str, chapter_number: str, order: str = "desc"):
    normalized_input = normalize_name(name)
    manhwa = None
    for doc in collection.find({}, {"name": 1, "_id": 1}):
        if "name" in doc and normalize_name(doc["name"]) == normalized_input:
            manhwa = collection.find_one({"_id": doc["_id"]})
            break
    if not manhwa:
        raise HTTPException(status_code=404, detail="Manhwa not found")
    chapters = manhwa.get("chapters", [])
    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found")
    # Allow order param: desc (default) or asc
    if order == "desc":
        chapters = list(reversed(chapters))
    chapternum_str = f"Chapter {chapter_number}"
    for chapter in chapters:
        if chapter.get("chapternum") == chapternum_str:
            return chapter
    raise HTTPException(status_code=404, detail="Chapter not found")



@app.get("/manhwa/count")
def get_manhwa_count():
    count = collection.count_documents({})
    return {"count": count}

@app.on_event("startup")
def test_db_connection():
    try:
        db.list_collection_names()
        count = collection.count_documents({})
        print(f"MongoDB connection successful. Documents in 'manhwa': {count}")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
# Place this endpoint after app = FastAPI() and all other endpoints


# To run: uvicorn main:app --reload
