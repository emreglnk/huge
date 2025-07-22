import logging
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import json
from datetime import datetime

from .db import db

def get_database():
    """Get database instance"""
    return db

logger = logging.getLogger(__name__)

class DatabaseTool:
    """MongoDB database operations tool for AI agents"""
    
    def __init__(self):
        self.db = db
    
    async def create_collection(self, collection_name: str, schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new collection with optional schema validation"""
        try:
            # Check if collection already exists
            collections = await self.db.list_collection_names()
            
            if collection_name in collections:
                return {"success": True, "message": f"Collection {collection_name} already exists"}
            
            # Create collection with schema validation if provided
            if schema:
                validator = {"$jsonSchema": schema}
                await self.db.create_collection(collection_name, validator=validator)
            else:
                await self.db.create_collection(collection_name)
            
            logger.info(f"Created collection: {collection_name}")
            return {"success": True, "message": f"Collection {collection_name} created successfully"}
            
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def insert_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a document into a collection"""
        try:
            collection = self.db[collection_name]
            
            # Add timestamp if not present
            if "created_at" not in document:
                document["created_at"] = datetime.utcnow().isoformat()
            
            result = await collection.insert_one(document)
            
            logger.info(f"Inserted document into {collection_name}: {result.inserted_id}")
            return {
                "success": True, 
                "inserted_id": str(result.inserted_id),
                "message": "Document inserted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error inserting document into {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def find_documents(self, collection_name: str, query: Dict[str, Any] = None, 
                           limit: int = 10, sort: Dict[str, Any] = None) -> Dict[str, Any]:
        """Find documents in a collection"""
        try:
            collection = self.db[collection_name]
            
            if query is None:
                query = {}
            
            cursor = collection.find(query)
            
            if sort:
                cursor = cursor.sort(list(sort.items()))
            
            cursor = cursor.limit(limit)
            
            documents = []
            async for doc in cursor:
                # Convert ObjectId to string for JSON serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                documents.append(doc)
            
            logger.info(f"Found {len(documents)} documents in {collection_name}")
            return {"success": True, "documents": documents, "count": len(documents)}
            
        except Exception as e:
            logger.error(f"Error finding documents in {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def update_document(self, collection_name: str, query: Dict[str, Any], 
                            update: Dict[str, Any]) -> Dict[str, Any]:
        """Update a document in a collection"""
        try:
            collection = self.db[collection_name]
            
            # Add update timestamp
            if "$set" in update:
                update["$set"]["updated_at"] = datetime.utcnow().isoformat()
            else:
                update["$set"] = {"updated_at": datetime.utcnow().isoformat()}
            
            result = await collection.update_one(query, update)
            
            logger.info(f"Updated document in {collection_name}: matched={result.matched_count}, modified={result.modified_count}")
            return {
                "success": True,
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "message": "Document updated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error updating document in {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def delete_document(self, collection_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a document from a collection"""
        try:
            collection = self.db[collection_name]
            
            result = await collection.delete_one(query)
            
            logger.info(f"Deleted document from {collection_name}: deleted_count={result.deleted_count}")
            return {
                "success": True,
                "deleted_count": result.deleted_count,
                "message": "Document deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting document from {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def aggregate(self, collection_name: str, pipeline: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform aggregation on a collection"""
        try:
            collection = self.db[collection_name]
            
            cursor = collection.aggregate(pipeline)
            
            results = []
            async for doc in cursor:
                # Convert ObjectId to string for JSON serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                results.append(doc)
            
            logger.info(f"Aggregation on {collection_name} returned {len(results)} results")
            return {"success": True, "results": results, "count": len(results)}
            
        except Exception as e:
            logger.error(f"Error in aggregation on {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def count_documents(self, collection_name: str, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Count documents in a collection"""
        try:
            collection = self.db[collection_name]
            
            if query is None:
                query = {}
            
            count = await collection.count_documents(query)
            
            logger.info(f"Counted {count} documents in {collection_name}")
            return {"success": True, "count": count}
            
        except Exception as e:
            logger.error(f"Error counting documents in {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics for a collection"""
        try:
            collection = self.db[collection_name]
            
            # Get collection stats
            stats = await self.db.command("collStats", collection_name)
            
            # Get document count
            count = await collection.count_documents({})
            
            # Get sample document for schema inference
            sample_doc = await collection.find_one({})
            
            result = {
                "success": True,
                "collection_name": collection_name,
                "document_count": count,
                "size": stats.get("size", 0),
                "avg_obj_size": stats.get("avgObjSize", 0),
                "sample_document": sample_doc
            }
            
            # Convert ObjectId to string if present
            if result["sample_document"] and "_id" in result["sample_document"]:
                result["sample_document"]["_id"] = str(result["sample_document"]["_id"])
            
            logger.info(f"Retrieved stats for collection {collection_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting stats for {collection_name}: {str(e)}")
            return {"success": False, "error": str(e)}

# Global database tool instance
database_tool = DatabaseTool()

# Tool execution functions for integration with tool_executor
async def execute_database_operation(operation: str, **kwargs) -> Dict[str, Any]:
    """Execute database operation"""
    try:
        if operation == "create_collection":
            return await database_tool.create_collection(
                kwargs.get("collection_name"),
                kwargs.get("schema")
            )
        elif operation == "insert_document":
            return await database_tool.insert_document(
                kwargs.get("collection_name"),
                kwargs.get("document")
            )
        elif operation == "find_documents":
            return await database_tool.find_documents(
                kwargs.get("collection_name"),
                kwargs.get("query"),
                kwargs.get("limit", 10),
                kwargs.get("sort")
            )
        elif operation == "update_document":
            return await database_tool.update_document(
                kwargs.get("collection_name"),
                kwargs.get("query"),
                kwargs.get("update")
            )
        elif operation == "delete_document":
            return await database_tool.delete_document(
                kwargs.get("collection_name"),
                kwargs.get("query")
            )
        elif operation == "aggregate":
            return await database_tool.aggregate(
                kwargs.get("collection_name"),
                kwargs.get("pipeline")
            )
        elif operation == "count_documents":
            return await database_tool.count_documents(
                kwargs.get("collection_name"),
                kwargs.get("query")
            )
        elif operation == "get_collection_stats":
            return await database_tool.get_collection_stats(
                kwargs.get("collection_name")
            )
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
            
    except Exception as e:
        logger.error(f"Error executing database operation {operation}: {str(e)}")
        return {"success": False, "error": str(e)} 