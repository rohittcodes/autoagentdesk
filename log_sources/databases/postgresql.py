from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
import asyncpg
from . import DatabaseLogSource

class PostgreSQLLogSource(DatabaseLogSource):
    """PostgreSQL log source implementation"""
    
    def _validate_config(self) -> None:
        super()._validate_config()
        required_fields = ["username", "password"]
        missing_fields = [field for field in required_fields if field not in self.config]
        if missing_fields:
            raise ValueError(f"Missing required PostgreSQL fields: {', '.join(missing_fields)}")
    
    async def connect(self) -> None:
        self.connection = await asyncpg.connect(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["username"],
            password=self.config["password"],
            database=self.config["database"]
        )
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.connection:
            await self.connect()
            
        query = f"SELECT * FROM {self.config['table']}"
        params = []
        
        if from_timestamp:
            query += " WHERE timestamp >= $1"
            params.append(from_timestamp)
            
        query += " ORDER BY timestamp ASC"
        
        async with self.connection.transaction():
            async for record in self.connection.cursor(query, *params):
                yield dict(record)
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not self.connection:
            await self.connect()
            
        query = f"SELECT * FROM {self.config['table']}"
        conditions = []
        params = []
        param_index = 1
        
        if start_time:
            conditions.append(f"timestamp >= ${param_index}")
            params.append(start_time)
            param_index += 1
            
        if end_time:
            conditions.append(f"timestamp <= ${param_index}")
            params.append(end_time)
            param_index += 1
            
        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = ${param_index}")
                params.append(value)
                param_index += 1
                
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
            
        rows = await self.connection.fetch(query, *params)
        return [dict(row) for row in rows]