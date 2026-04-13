import os
import pymongo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")

if not MONGODB_URL:
    print("❌ MONGODB_URL not found in .env file.")
    exit(1)

try:
    # Create a client with a short timeout
    client = pymongo.MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    
    # Ping the server to check connectivity
    client.admin.command('ping')
    
    print("✅ Successfully connected to MongoDB!")
    
    # Check databases
    db_names = client.list_database_names()
    print(f"📂 Available databases: {', '.join(db_names)}")
    
    if "users" in db_names:
        db = client["users"]
        collections = db.list_collection_names()
        print(f"📦 Collections in 'users' database: {', '.join(collections)}")
    else:
        print("⚠️  'users' database not found.")

except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
