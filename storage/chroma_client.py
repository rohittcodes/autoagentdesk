# storage/chroma_client.py
import chromadb
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from chromadb.utils import embedding_functions
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class ChromaLogStore:
    def __init__(self, db_path: str, google_api_key: str, collection_name: str = "logs", retention_days: int = 30):
        # Initialize Chroma client
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Configure the Google Generative AI SDK
        genai.configure(api_key=google_api_key)
        
        # Initialize Google's embeddings
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            google_api_key=google_api_key,
            model="models/embedding-001"
        )
        
        # Create a proper embedding function for ChromaDB
        class GeminiEmbeddingFunction(embedding_functions.EmbeddingFunction):
            def __init__(self, embedding_model):
                self.embedding_model = embedding_model
                
            def __call__(self, texts):
                """
                Generate embeddings for a list of texts
                """
                if not texts:
                    return []
                # Return embeddings as a list of lists of floats
                return self.embedding_model.embed_documents(texts)
        
        # Create the embedding function
        self.embedding_func = GeminiEmbeddingFunction(self.embedding_model)
        
        # Initialize or get the collection
        try:
            self.collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_func
            )
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_func
            )
        
        self.retention_days = retention_days
    
    async def store_logs(self, logs: List[Dict[str, Any]]):
        """Store a batch of logs in Chroma DB"""
        documents = []
        metadatas = []
        ids = []
        
        for log in logs:
            # Prepare the data
            log_id = f"{log.get('producer_id', 'unknown')}_{int(time.time())}_{len(documents)}"
            log_text = f"{log.get('level', 'INFO')} - {log.get('service', 'unknown')} - {log.get('message', '')}"
            
            # Prepare metadata (includes timestamp for time-series queries)
            metadata = {
                "timestamp": log.get("timestamp", datetime.utcnow().isoformat()),
                "level": str(log.get("level", "INFO")),  # Convert to string
                "service": str(log.get("service", "unknown")),  # Convert to string
                "producer_id": str(log.get("producer_id", "unknown")),  # Convert to string
            }
            
            # Add any additional metadata
            if "metadata" in log and isinstance(log["metadata"], dict):
                for key, value in log["metadata"].items():
                    # Handle null values and ensure all values are strings, numbers, or booleans
                    if value is None:
                        metadata[f"metadata_{key}"] = "null"
                    elif isinstance(value, (str, int, float, bool)):
                        metadata[f"metadata_{key}"] = value
                    else:
                        metadata[f"metadata_{key}"] = str(value)
            
            documents.append(log_text)
            metadatas.append(metadata)
            ids.append(log_id)
        
        # Store in Chroma DB
        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
    
    async def cleanup_old_logs(self):
        """Remove logs older than retention period"""
        cutoff_date = (datetime.utcnow() - timedelta(days=self.retention_days)).isoformat()
        
        # Chroma doesn't support direct timestamp-based deletion
        # This is a simplified approach - in production we might want to 
        # implement a more efficient cleanup strategy
        results = self.collection.query(
            query_texts=[""],
            n_results=10000,  # Set a reasonable limit
            where={"timestamp": {"$lt": cutoff_date}}
        )
        
        if results and results['ids']:
            # Flatten the list of lists
            ids_to_delete = [id for sublist in results['ids'] for id in sublist]
            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
    
    async def query_logs(
        self, 
        query: Optional[str] = None, 
        filters: Optional[Dict] = None, 
        time_range: Optional[Dict] = None,
        limit: int = 100
    ):
        """Query logs with semantic search and/or metadata filtering"""
        try:
            # Build the where clause according to ChromaDB's expected format
            conditions = []
            
            # Add filters to conditions
            if filters:
                for key, value in filters.items():
                    # Map filter keys to the correct ChromaDB metadata fields
                    # For example, 'service_name' should be 'service'
                    if key == 'service_name':
                        key = 'service'
                    elif key == 'log_level':
                        key = 'level'
                        
                    # Handle multiple values for a single key (e.g., ['ERROR', 'WARN'])
                    if isinstance(value, list) and len(value) > 1:
                        # Use $in operator for multiple values
                        conditions.append({key: {"$in": value}})
                    elif isinstance(value, list) and len(value) == 1:
                        # Use $eq for a single value in a list
                        conditions.append({key: {"$eq": value[0]}})
                    else:
                        # Use $eq for a single value
                        conditions.append({key: {"$eq": value}})
                    
            # Add time range conditions
            if time_range:
                if "start" in time_range:
                    conditions.append({"timestamp": {"$gte": time_range["start"]}})
                if "end" in time_range:
                    conditions.append({"timestamp": {"$lte": time_range["end"]}})
                
            # Combine all conditions with $and if there are multiple conditions
            where_clause = {}
            if conditions:
                if len(conditions) == 1:
                    # If there's only one condition, use it directly
                    where_clause = conditions[0]
                else:
                    # If there are multiple conditions, use $and
                    where_clause = {"$and": conditions}
                
            # Debug: Print the constructed where clause
            print(f"DEBUG - Constructed where clause: {where_clause}")

            # Execute query
            # Fix: Ensure query_text is a string, not a list or other type
            if query is None:
                query_text = ""
            elif isinstance(query, str):
                query_text = query
            elif isinstance(query, list):
                # If it's a list, convert it to a string
                if query and len(query) > 0:
                    query_text = str(query[0])
                else:
                    query_text = ""
            else:
                # For any other type, convert to string
                query_text = str(query)
                
            print(f"DEBUG - Executing query with text: '{query_text}'")
            
            # Skip the where clause if it's empty
            if not where_clause:
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=limit
                )
            else:
                results = self.collection.query(
                    query_texts=[query_text],
                    where=where_clause,
                    n_results=limit
                )
            
            # Transform results to a more usable format
            logs = []
            if results and 'ids' in results and results['ids'] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    # Skip empty results
                    if i >= len(results["metadatas"][0]):
                        continue
                        
                    metadata = results["metadatas"][0][i]
                    document = results["documents"][0][i] if results["documents"] and len(results["documents"]) > 0 else ""
                    
                    # Extract original metadata fields
                    log_metadata = {}
                    for key, value in metadata.items():
                        if key.startswith("metadata_"):
                            log_metadata[key[9:]] = value  # Remove the "metadata_" prefix
                    
                    log_entry = {
                        "timestamp": metadata.get("timestamp"),
                        "level": metadata.get("level"),
                        "service": metadata.get("service"),
                        "producer_id": metadata.get("producer_id"),
                        "message": document,
                        "metadata": log_metadata
                    }
                    logs.append(log_entry)
            
            print(f"DEBUG - Query returned {len(logs)} logs")
            return logs
        except Exception as e:
            import traceback
            print(f"ERROR in ChromaLogStore.query_logs: {str(e)}")
            print(traceback.format_exc())
            # Re-raise the exception to be handled by the API route
            raise