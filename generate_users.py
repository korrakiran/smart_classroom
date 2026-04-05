import pymongo
import datetime

def seed_users():
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["smart_classroom"]
    users = db["users"]
    
    users.create_index("email", unique=True)
    
    test_users = [
        {
            "email": "teacher@smartclassroom.edu",
            "password": None,
            "passwordCreatedAt": None,
            "lastLoginAt": None,
            "loginAttempts": 0,
            "lockedUntil": None,
            "createdAt": datetime.datetime.utcnow(),
            "updatedAt": datetime.datetime.utcnow()
        },
        {
            "email": "admin@smartclassroom.edu",
            "password": None,
            "passwordCreatedAt": None,
            "lastLoginAt": None,
            "loginAttempts": 0,
            "lockedUntil": None,
            "createdAt": datetime.datetime.utcnow(),
            "updatedAt": datetime.datetime.utcnow()
        }
    ]
    
    for u in test_users:
        try:
            users.insert_one(u)
            print(f"Added test user: {u['email']}")
        except pymongo.errors.DuplicateKeyError:
            print(f"User already exists: {u['email']}")

if __name__ == "__main__":
    seed_users()
