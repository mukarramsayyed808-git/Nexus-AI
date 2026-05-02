from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os, sys

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = "nexusai_v6"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    print(f"✅  MongoDB connected → {MONGO_URI}")
except ConnectionFailure:
    print("❌  MongoDB connection failed. Is MongoDB running?")
    sys.exit(1)

db = client[DB_NAME]

# ── Indexes ────────────────────────────────────────────────────────
db.users.create_index([("email", ASCENDING)], unique=True)
db.admins.create_index([("username", ASCENDING)], unique=True)
db.chat_history.create_index([("user_email", ASCENDING)])
db.chat_history.create_index([("created_at", DESCENDING)])
db.chat_history.create_index([("tool", ASCENDING)])
db.chat_history.create_index([("model", ASCENDING)])

print(f"📦  Database   : {DB_NAME}")
print(f"📁  Collections: users, admins, chat_history")