from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
import aiosqlite
from . import DatabaseLogSource

class SQLiteLogSource(DatabaseLogSource):
    """SQLite log source implementation"""
    
    def _validate_config(self) -> None:
        if "database" not in self.config:
            raise ValueError("Missing required field: database (path to SQLite file)")
    
    async def connect(self) -> None:
        self.connection = await aiosqlite.connect(self.config["database"])
        # Enable dictionary rows
        self.connection.row_factory = aiosqlite.Row
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.connection:
            await self.connect()
            
        query = f"SELECT * FROM {self.config.get('table', 'logs')}"
        params = []
        
        if from_timestamp:
            query += " WHERE timestamp >= ?"
            params.append(from_timestamp.isoformat())
            
        query += " ORDER BY timestamp ASC"
        
        async with self.connection.execute(query, params) as cursor:
            async for row in cursor:
                yield dict(row)
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not self.connection:
            await self.connect()
            
        query = f"SELECT * FROM {self.config.get('table', 'logs')}"
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())
            
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())
            
        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = ?")
                params.append(value)
                
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
            
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]