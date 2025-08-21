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
    allow_origins=["*"],
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
    projection = {"name": 1, "last_chapter": 1, "rating": 1, "cover_image": 1, "posted_on": 1, "_id": 0}
    # Sort by posted_on (if date), else fallback to _id for newest first
    manhwa_cursor = collection.find(query, projection).sort([("posted_on", -1), ("_id", -1)]).skip(skip).limit(limit)
    total = collection.count_documents(query)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": list(manhwa_cursor)
    }

@app.get("/manhwa/search")
def search_manhwa(query: str, page: int = 1, limit: int = 20):
    query_str = normalize_name(query)
    skip = (page - 1) * limit
    regex = f"^{query_str}"  # Prefix match for faster search
    projection = {"name": 1, "last_chapter": 1, "rating": 1, "cover_image": 1, "_id": 0}
    manhwa_cursor = collection.find({"name": {"$regex": regex, "$options": "i"}}, projection).sort([("posted_on", -1), ("_id", -1)]).skip(skip).limit(limit)
    total = collection.count_documents({"name": {"$regex": regex, "$options": "i"}})
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": list(manhwa_cursor)
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
def get_chapter_detail(name: str, chapter_number: int, order: str = "desc"):
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
    if chapter_number < 1 or chapter_number > len(chapters):
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapters[chapter_number - 1]

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

# To run: uvicorn main:app --reload
