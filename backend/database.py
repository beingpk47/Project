from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        try:
            mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/speechbot_saas")
            self.client = MongoClient(mongodb_uri)
            self.db = self.client.speechbot_saas
            print("Connected to MongoDB successfully")
        except ConnectionFailure as e:
            print(f"Could not connect to MongoDB: {e}")
    
    def get_collection(self, collection_name):
        return self.db[collection_name]
    
    

db = Database()