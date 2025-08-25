# Backend API

## FastAPI Endpoints
- `/manhwa` — List manhwa with filters, caching
- `/manhwa/search` — Fuzzy search with synonyms
- `/manhwa/{name}` — Manhwa details
- `/manhwa/{name}/chapters` — List chapters
- `/manhwa/{name}/chapters/{chapter_number}` — Chapter details
- `/manhwa/count` — Total count

## Features
- MongoDB integration
- Redis caching for homepage
- Fuzzy search (fuzzywuzzy)
- Synonym support (see `synonyms.py`)
- CORS setup for allowed domains
- Error handling and serialization

See `main.py` for implementation details.
