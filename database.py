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
            
            # Initialize database collections and indexes
            self.init_database()
            
        except ConnectionFailure as e:
            print(f"Could not connect to MongoDB: {e}")
    
    def init_database(self):
        """Initialize database with required collections and indexes"""
        # Collections to create
        collections = ["user_questions", "question_requests", "question_stats"]
        
        print("🔄 Initializing database...")
        
        for collection_name in collections:
            if collection_name not in self.db.list_collection_names():
                self.db.create_collection(collection_name)
                print(f"✅ Created collection: {collection_name}")
        
        # Create indexes for better performance
        self.create_indexes()
        
        # Migrate existing data if needed
        self.migrate_existing_data()
        
        print("🎉 Database initialization completed!")
    
    def create_indexes(self):
        """Create necessary indexes for better performance"""
        try:
            # User questions indexes
            self.db.user_questions.create_index([("client_id", 1), ("question", 1)])
            self.db.user_questions.create_index([("client_id", 1), ("is_valid", 1)])
            self.db.user_questions.create_index([("client_id", 1), ("requested_by_client", 1)])
            self.db.user_questions.create_index([("created_at", -1)])
            
            # Question requests indexes
            self.db.question_requests.create_index([("client_id", 1), ("status", 1)])
            self.db.question_requests.create_index([("status", 1)])
            self.db.question_requests.create_index([("created_at", -1)])
            self.db.question_requests.create_index([("request_type", 1)])
            
            # Questions indexes
            self.db.questions.create_index([("client_id", 1)])
            self.db.questions.create_index([("website", 1)])
            self.db.questions.create_index([("created_at", -1)])
            
            # Clients indexes
            self.db.clients.create_index([("website", 1)])
            self.db.clients.create_index([("email", 1)])
            self.db.clients.create_index([("subscription_plan", 1)])
            
            # Notifications indexes
            self.db.notifications.create_index([("user_id", 1), ("is_read", 1)])
            self.db.notifications.create_index([("created_at", -1)])
            self.db.notifications.create_index([("type", 1)])
            
            print("✅ Database indexes created successfully")
            
        except Exception as e:
            print(f"❌ Error creating indexes: {e}")
    
    def migrate_existing_data(self):
        """Migrate existing data to new schema if needed"""
        try:
            # Check if we need to add user_hits fields to existing clients
            clients = self.db.clients.find({"user_hits_allowed": {"$exists": False}})
            
            count = 0
            for client in clients:
                # Set default values for existing clients
                plan_limits = {
                    "trial": {"user_hits_allowed": 50},
                    "monthly": {"user_hits_allowed": 100},
                    "quarterly": {"user_hits_allowed": 400},
                    "yearly": {"user_hits_allowed": 1200}
                }
                
                current_plan = client.get("subscription_plan", "trial")
                user_hits_allowed = plan_limits.get(current_plan, plan_limits["trial"])["user_hits_allowed"]
                
                self.db.clients.update_one(
                    {"_id": client["_id"]},
                    {
                        "$set": {
                            "user_hits_allowed": user_hits_allowed,
                            "user_hits_used": 0
                        }
                    }
                )
                count += 1
            
            if count > 0:
                print(f"✅ Migrated {count} clients with user hits data")
            
        except Exception as e:
            print(f"❌ Error during data migration: {e}")
    
    def get_collection(self, collection_name):
        return self.db[collection_name]
    

db = Database()