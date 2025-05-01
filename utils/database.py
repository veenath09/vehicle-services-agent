import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """
    Connect to MongoDB using connection string from environment variables
    Returns the database instance for the Servio database
    """
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        raise ValueError("MONGODB_URI environment variable not set")
    
    client = MongoClient(mongodb_uri)
    db = client.get_database()  # This gets the database specified in the URI
    return db