"""
MongoDB Service
"""
from pymongo import MongoClient, UpdateOne
from typing import List, Dict
from datetime import datetime
from config.settings import MONGODB_URI, DATABASE_NAME
from utils.logger import get_logger

logger = get_logger(__name__)


class MongoDBService:
    def __init__(self, uri: str = MONGODB_URI, db_name: str = DATABASE_NAME):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        logger.info(f"Connected to MongoDB database: {db_name}")
    
    def insert_places(self, collection_name: str, places: List[Dict]) -> int:
        """
        Insert or update places in MongoDB collection using upsert
        """
        if not places:
            logger.warning(f"No places to insert in {collection_name}")
            return 0
        
        collection = self.db[collection_name]
        
        # Prepare bulk operations
        operations = []
        for place in places:
            # Add metadata
            place['last_updated'] = datetime.utcnow()
            
            # Upsert based on place_id
            operations.append(
                UpdateOne(
                    {'place_id': place['place_id']},
                    {'$set': place},
                    upsert=True
                )
            )
        
        try:
            result = collection.bulk_write(operations)
            inserted_count = result.upserted_count
            modified_count = result.modified_count
            
            logger.info(
                f"Collection '{collection_name}': "
                f"{inserted_count} inserted, {modified_count} updated"
            )
            return inserted_count + modified_count
            
        except Exception as e:
            logger.error(f"Error inserting data into {collection_name}: {e}")
            return 0
    
    def get_collection_stats(self, collection_name: str) -> Dict:
        """
        Get statistics about a collection
        """
        collection = self.db[collection_name]
        
        return {
            'collection': collection_name,
            'total_documents': collection.count_documents({}),
            'last_updated': collection.find_one(
                sort=[('last_updated', -1)]
            )
        }
    
    def create_indexes(self, collection_name: str):
        """
        Create indexes for better query performance
        """
        collection = self.db[collection_name]
        
        # Create indexes
        collection.create_index('place_id', unique=True)
        collection.create_index('name')
        collection.create_index([('coordinates.lat', 1), ('coordinates.lng', 1)])
        collection.create_index('last_updated')
        
        logger.info(f"Indexes created for collection: {collection_name}")
    
    def clear_collection(self, collection_name: str):
        """
        Clear all documents from a collection
        """
        collection = self.db[collection_name]
        result = collection.delete_many({})
        logger.info(f"Cleared {result.deleted_count} documents from {collection_name}")
    
    def close(self):
        """
        Close MongoDB connection
        """
        self.client.close()
        logger.info("MongoDB connection closed")