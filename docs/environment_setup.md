# Environment Setup

## Requirements
- Python 3.11+
- MongoDB (remote or local)
- Redis
- Node.js (if using frontend build tools)

## Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## MongoDB & Redis
- Ensure MongoDB is running and accessible at the configured URI.
- Start Redis server: `redis-server`

## Environment Variables
- Set `MONGO_URI` in your environment or `.env` file if needed.
