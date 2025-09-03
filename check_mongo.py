
from pymongo import MongoClient
from dotenv import load_dotenv
import os

def get_mongo_client():
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    return MongoClient(uri)

client = get_mongo_client()
db = client["admin"]
collection = db["manhwa"]

def check_connection_and_data():
    try:
        # Test connection
        db.list_collection_names()
        print("MongoDB connection successful.")
        # Check for data
        count = collection.count_documents({})
        print(f"Documents in 'manhwa' collection: {count}")
        if count > 0:
            sample = collection.find_one({})
            print("Sample document:")
            print(sample)
        else:
            print("No documents found in 'manhwa' collection.")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")

if __name__ == "__main__":
    check_connection_and_data()
