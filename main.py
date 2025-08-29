
from fuzzywuzzy import fuzz
from synonyms import SYNONYMS
# Find chapter images by chapternum match

# ...existing code...


from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
    allow_origins=["https://manhwagalaxy.org", "http://165.232.60.4:3001","http://192.168.0.102:3000/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable gzip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=500)


# MongoDB connection (admin database)
client = get_mongo_client()
db = client["admin"]
collection = db["manhwa"]
# Contact Us collection
contact_collection = db["contact_us"]
# ...existing code...

# Contact Us Models
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class ContactMessage(BaseModel):
    name: str = Field(..., example="John Doe")
    email: EmailStr = Field(..., example="john@example.com")
    message: str = Field(..., example="Your message here.")
    status: str = Field(default="new", example="new")
    category: str = Field(..., example="General Inquiry")

class ContactMessageOut(ContactMessage):
    id: str
    created_at: datetime

# Allowed status and categories
CONTACT_STATUS = ["new", "in-progress", "resolved"]
CONTACT_CATEGORIES = [
    "General Inquiry",
    "Feedback / Suggestions",
    "Bug / Technical Issue",
    "Content Request",
    "Partnership / Collaboration",
    "Account / Login Issue",
    "Other"
]

# POST endpoint to submit contact message
@app.post("/contact_us", response_model=ContactMessageOut)
def submit_contact_message(data: ContactMessage):
    doc = data.dict()
    doc["created_at"] = datetime.utcnow()
    result = contact_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return ContactMessageOut(**doc)

# GET endpoint to list contact messages (open, no auth)
@app.get("/contact_us", response_model=List[ContactMessageOut])
def list_contact_messages(status: Optional[str] = None, category: Optional[str] = None, page: int = 1, limit: int = 20):
    query = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    skip = (page - 1) * limit
    cursor = contact_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    results = []
    for doc in cursor:
        doc["id"] = str(doc["_id"])
        results.append(ContactMessageOut(**doc))
    return results

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
import hashlib
from datetime import datetime, timezone
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from collections import OrderedDict

# Redis connection (default settings, adjust as needed)
redis_client = redis.Redis(host='localhost', port=6379, db=0)
def normalize_name(name: str) -> str:
    # Remove non-alphanumeric, lowercase
    name = unquote(name)
    name = re.sub(r'[^A-Za-z0-9]', '', name)
    return name.lower()

# Simple in-memory TTL cache with LRU eviction
class TTLCache:
    def __init__(self, maxsize: int = 512):
        self.maxsize = maxsize
        self.store: OrderedDict[str, dict] = OrderedDict()

    def get(self, key: str):
        now = datetime.now(timezone.utc).timestamp()
        item = self.store.get(key)
        if not item:
            return None
        if item["exp"] < now:
            self.store.pop(key, None)
            return None
        # touch
        self.store.move_to_end(key)
        return item

    def set(self, key: str, value: dict, ttl: int):
        now = datetime.now(timezone.utc).timestamp()
        value = {**value, "exp": now + ttl}
        self.store[key] = value
        self.store.move_to_end(key)
        # evict
        while len(self.store) > self.maxsize:
            self.store.popitem(last=False)

    def ttl_left(self, key: str) -> int:
        item = self.store.get(key)
        if not item:
            return 0
        now = datetime.now(timezone.utc).timestamp()
        return max(0, int(item["exp"] - now))

suggest_cache = TTLCache(maxsize=1024)

def _make_slug(name: str) -> str:
    # simple slug from name
    return re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", name.strip().lower()))

def _rate_limited(ip: str, limit: int = 60, window: int = 60) -> bool:
    try:
        key = f"rl:suggest:{ip}:{int(datetime.utcnow().timestamp() // window)}"
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, window)
        return current > limit
    except Exception:
        # If redis is down, do not block
        return False

def _hash_etag(payload: dict) -> str:
    raw = JSONResponse(content=payload).body or b""
    return '"' + hashlib.md5(raw).hexdigest() + '"'

@app.get("/manhwa/suggest")
def suggest(request: Request, response: Response, prefix: str = "", limit: int = 8, fields: Optional[str] = "name"):
    try:
        # Enforce minimal prefix length
        if not prefix or len(prefix.strip()) < 2:
            response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
            return Response(status_code=204)

        ip = request.client.host if request.client else "unknown"
        if _rate_limited(ip, limit=60, window=60):
            # soft-fail on rate limit
            payload = {"items": [], "cachedAt": datetime.utcnow().isoformat() + "Z", "ttl": 60}
            etag = _hash_etag(payload)
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
            return payload

        # Clamp limit
        limit = max(1, min(limit, 10))
        fields_req = set([f.strip() for f in (fields or "name").split(",") if f.strip()])

        key = f"suggest:{prefix.lower()}:{limit}:{','.join(sorted(fields_req))}"
        cached = suggest_cache.get(key)
        if cached:
            payload = {k: v for k, v in cached.items() if k != "exp"}
            payload["ttl"] = suggest_cache.ttl_left(key)
            etag = _hash_etag(payload)
            inm = request.headers.get("if-none-match")
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=30"
            if inm == etag:
                return Response(status_code=304)
            return payload

        # Query MongoDB: startswith first
        rx_prefix = re.compile(f"^{re.escape(prefix)}", re.IGNORECASE)
        rx_contains = re.compile(re.escape(prefix), re.IGNORECASE)
        projection = {"name": 1, "url": 1, "_id": 0}
        starts = list(collection.find({"name": {"$regex": rx_prefix}}, projection).max_time_ms(200).limit(limit * 3))
        items = starts[:]
        if len(items) < limit:
            # fetch a few more candidates that contain the prefix
            contains = list(collection.find({"name": {"$regex": rx_contains}}, projection).max_time_ms(200).limit(100))
            # Fuzzy rank remaining candidates not already included
            seen_names = set(doc.get("name", "") for doc in items)
            for doc in contains:
                name = doc.get("name", "")
                if name in seen_names or rx_prefix.match(name):
                    continue
                score = fuzz.partial_ratio(prefix.lower(), name.lower())
                if score >= 80:
                    items.append(doc)
                if len(items) >= limit * 3:
                    break

        # Build response items
        out = []
        for doc in items:
            entry = {}
            if "name" in fields_req:
                entry["name"] = doc.get("name")
            if "slug" in fields_req:
                slug = doc.get("url") or _make_slug(doc.get("name", ""))
                entry["slug"] = slug
            # default to name if fields not set properly
            if not entry:
                entry["name"] = doc.get("name")
            out.append(entry)
            if len(out) >= limit:
                break

        payload = {"items": out, "cachedAt": datetime.utcnow().isoformat() + "Z", "ttl": 300}
        etag = _hash_etag(payload)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=30"
        suggest_cache.set(key, payload, ttl=300)
        return payload
    except Exception:
        # Never 500 to clients for suggest
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
        return {"items": [], "cachedAt": datetime.utcnow().isoformat() + "Z", "ttl": 60}

@app.get("/manhwa")
def get_manhwa_list(genre: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None, page: int = 1, limit: int = 20):
    query = {}
    # Flexible genre filter: support string or array (comma-separated)
    if genre:
        # Accept comma-separated genres as array, or single string
        if "," in genre:
            genre_list = [g.strip() for g in genre.split(",") if g.strip()]
            query["genres"] = {"$in": genre_list}
        else:
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
def search_manhwa(query: Optional[str] = None, page: int = 1, limit: int = 20, genre: Optional[str] = None):
    skip = (page - 1) * limit
    projection = {"name": 1, "last_chapter": 1, "rating": 1, "cover_image": 1, "posted_on": 1, "updated_at": 1, "_id": 0}

    # Expand query with synonyms if query is provided
    search_terms = []
    if query:
        query_str = normalize_name(query)
        search_terms = [query_str]
        for key, values in SYNONYMS.items():
            if query_str == key or query_str in values:
                search_terms.extend([key] + values)

    # Flexible genre filter: support string or array (comma-separated)
    mongo_query = {}
    if genre:
        if "," in genre:
            genre_list = [g.strip() for g in genre.split(",") if g.strip()]
            mongo_query["genres"] = {"$in": genre_list}
        else:
            mongo_query["genres"] = genre

    # Fetch all candidates matching genre (limit for performance)
    candidates = list(collection.find(mongo_query, projection))
    matched = []
    if search_terms:
        # Fuzzy match if query is provided
        for doc in candidates:
            name = doc.get("name", "").lower()
            for term in search_terms:
                score = fuzz.partial_ratio(term, name)
                if score >= 80:
                    matched.append(doc)
                    break
    else:
        # If no query, return all candidates (filtered by genre)
        matched = candidates

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
# Global error handler to avoid exposing internal errors
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.exception_handlers import RequestValidationError
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the error here if needed
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please contact support if this persists."}
    )
