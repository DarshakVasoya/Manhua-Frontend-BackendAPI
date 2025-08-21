# Manhwa Backend API

A FastAPI backend for serving manhwa/manga data from MongoDB, designed for frontend sites like kingofshojo.com.

## Features
- List all manhwa/manga with pagination and filters
- Search by name (fast, indexed)
- Get details for a manhwa (excluding chapters)
- Get chapters for a manhwa (excluding images)
- Get details for a chapter
- Count total manhwa
- All endpoints support readable URLs (hyphens for spaces)
- Sort by latest updated (newest first)

## Endpoints

### List Manhwa
`GET /manhwa?page=1&limit=20&genre=Romance&type=Manhwa&status=Ongoing`
Returns paginated, filtered list sorted by latest update.

### Search Manhwa
`GET /manhwa/search?query=Hero&page=1&limit=20`
Returns paginated search results (prefix match, fast).

### Manhwa Details
`GET /manhwa/{name}`
Returns details for a manhwa (no chapters).

### Chapters List
`GET /manhwa/{name}/chapters?order=desc`
Returns chapter list (no images). `order=asc` for oldest first.

### Chapter Details
`GET /manhwa/{name}/chapters/{chapter_number}?order=desc`
Returns details for a chapter. `order=asc` for oldest first.

### Count
`GET /manhwa/count`
Returns total number of manhwa in the database.

## Data Model Example
```json
{
  "name": "Shall We Get Married?",
  "cover_image": "https://...",
  "rating": "8.9",
  "last_chapter": "Chapter 44",
  "description": "...",
  "genres": ["Romance", "Drama"],
  "posted_on": "August 21, 2025",
  "chapters": [
    {
      "link": "...",
      "chapternum": "Chapter 1",
      "chapterdate": "August 21, 2025",
      "images": ["...", "..."]
    }
  ]
}
```

## Running Locally
1. Install dependencies:
   ```bash
   pip install fastapi uvicorn pymongo
   ```
2. Set up MongoDB and configure your connection string in `main.py` or via `MONGO_URI` env variable.
3. Start the server:
   ```bash
   uvicorn main:app --reload
   ```
4. Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for API documentation.

## Notes
- Make sure your MongoDB has an index on `name` for fast search.
- Store `posted_on` as a date for best sorting (currently string, can be improved).
- All endpoints return lightweight, frontend-friendly data.

---
GitHub Copilot
