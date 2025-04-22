from log_sources import LogSource
import asyncio
import logging
import importlib
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
import json

logger = logging.getLogger(__name__)

class DatabaseLogSource(LogSource):
    """
    A log source for extracting logs from database tables.
    Supports various database engines including PostgreSQL, MySQL, SQLite,
    and cloud providers like Supabase and NeonDB.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a database log source.
        
        Args:
            config: A dictionary containing the database configuration with keys:
                - db_type: The database type (postgresql, mysql, sqlite, supabase, neon)
                - uri: Optional database connection string
                - host: Database host (if uri not provided)
                - port: Database port (if uri not provided)
                - database: Database name (if uri not provided)
                - username: Database username (if uri not provided)
                - password: Database password (if uri not provided)
                - log_query: SQL query to fetch logs or table name (can be any table name)
                - field_mappings: Mappings from DB column names to log fields
                - last_timestamp: Optional timestamp to fetch logs after
        """
        self.db_type = config.get('db_type', 'postgresql')
        self.uri = config.get('uri')
        self.host = config.get('host')
        self.port = config.get('port')
        self.database = config.get('database')
        self.username = config.get('username')
        self.password = config.get('password')
        self.log_query = config.get('log_query', '')
        
        # If log_query is empty, use a generic query that works on any table with timestamp
        if not self.log_query:
            # User can specify a table name to use
            table_name = config.get('table_name')
            if table_name:
                self.log_query = table_name
        
        # Field mappings define how database columns map to log fields
        # This allows flexibility for any table structure
        self.field_mappings = config.get('field_mappings', {
            'timestamp': config.get('timestamp_field', 'timestamp'),
            'level': config.get('level_field', 'level'),
            'message': config.get('message_field', 'message'),
            'service': config.get('service_field', 'service')
        })
        
        self.last_timestamp = config.get('last_timestamp')
        self.connection = None
        self.cursor = None
        
        super().__init__(config)
        
    def _validate_config(self) -> None:
        """Validate the configuration for this log source"""
        if not self.uri and not (self.host and self.database):
            raise ValueError("Either connection URI or host/database must be provided")
            
        # Allow empty log_query if table_name is provided
        if not self.log_query and not self.config.get('table_name'):
            # Try to discover available tables
            logger.info("No log table or query specified. Will attempt to discover tables at connection time.")
    
    async def connect(self) -> bool:
        """
        Establish a connection to the database.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            # Dynamically import the appropriate database driver
            if self.db_type == 'postgresql':
                import asyncpg
                if self.uri:
                    self.connection = await asyncpg.connect(self.uri)
                else:
                    self.connection = await asyncpg.connect(
                        host=self.host,
                        port=int(self.port) if self.port and self.port.strip() else 5432,
                        user=self.username,
                        password=self.password,
                        database=self.database
                    )
                return True
                
            elif self.db_type == 'mysql':
                import aiomysql
                if self.uri:
                    # Parse URI for aiomysql
                    # mysql://user:pass@host:port/database
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(self.uri)
                    
                    self.connection = await aiomysql.connect(
                        host=parsed.hostname,
                        port=parsed.port or 3306,
                        user=parsed.username,
                        password=parsed.password,
                        db=parsed.path.strip('/'),
                        autocommit=True
                    )
                else:
                    self.connection = await aiomysql.connect(
                        host=self.host,
                        port=int(self.port) if self.port and self.port.strip() else 3306,
                        user=self.username,
                        password=self.password,
                        db=self.database,
                        autocommit=True
                    )
                self.cursor = await self.connection.cursor(aiomysql.DictCursor)
                return True
                
            elif self.db_type == 'sqlite':
                import aiosqlite
                import sqlite3
                
                db_path = self.uri or self.database
                self.connection = await aiosqlite.connect(db_path)
                # Enable dict factory
                self.connection.row_factory = aiosqlite.Row
                return True
                
            elif self.db_type == 'supabase':
                # For Supabase we use the PostgreSQL interface with extra headers
                import asyncpg
                
                # Extract API key from URI or use directly if provided in password
                from urllib.parse import urlparse
                if self.uri:
                    parsed = urlparse(self.uri)
                    api_key = parsed.password
                    self.connection = await asyncpg.connect(
                        host=parsed.hostname,
                        port=parsed.port or 5432,
                        user=parsed.username,
                        password=api_key,
                        database=parsed.path.strip('/')
                    )
                else:
                    self.connection = await asyncpg.connect(
                        host=self.host,
                        port=int(self.port) if self.port and self.port.strip() else 5432,
                        user=self.username,
                        password=self.password,  # API key for Supabase
                        database=self.database
                    )
                return True
                
            elif self.db_type == 'neon':
                # Neon uses PostgreSQL protocol
                import asyncpg
                if self.uri:
                    self.connection = await asyncpg.connect(self.uri)
                else:
                    self.connection = await asyncpg.connect(
                        host=self.host,
                        port=int(self.port) if self.port and self.port.strip() else 5432,
                        user=self.username,
                        password=self.password,
                        database=self.database
                    )
                return True
                
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
                
        except Exception as e:
            logger.error(f"Error connecting to {self.db_type} database: {str(e)}")
            raise
    
    async def disconnect(self) -> None:
        """
        Close the database connection.
        """
        try:
            if self.cursor:
                await self.cursor.close()
                
            if self.connection:
                if self.db_type == 'mysql':
                    self.connection.close()
                else:
                    await self.connection.close()
                    
            self.connection = None
            self.cursor = None
        except Exception as e:
            logger.error(f"Error disconnecting from database: {str(e)}")
    
    def _build_query(self) -> str:
        """
        Build the SQL query to fetch logs based on the provided query/table and last timestamp.
        
        Returns:
            str: The SQL query to execute
        """
        # If log_query is a simple table name, build a SELECT query
        if ' ' not in self.log_query and ';' not in self.log_query:
            table_name = self.log_query
            timestamp_field = self.field_mappings.get('timestamp', 'timestamp')
            
            # Start with basic query
            query = f"SELECT * FROM {table_name}"
            
            # Add timestamp filter if needed
            if self.last_timestamp:
                query += f" WHERE {timestamp_field} > '{self.last_timestamp}'"
                
            # Add order by
            query += f" ORDER BY {timestamp_field} DESC LIMIT 100"
            
            return query
        else:
            # Use the provided query as is, but add timestamp filter if needed
            query = self.log_query
            
            if self.last_timestamp and 'WHERE' not in query.upper():
                timestamp_field = self.field_mappings.get('timestamp', 'timestamp')
                
                if 'ORDER BY' in query.upper():
                    # Insert WHERE before ORDER BY
                    parts = query.split('ORDER BY', 1)
                    query = f"{parts[0]} WHERE {timestamp_field} > '{self.last_timestamp}' ORDER BY {parts[1]}"
                else:
                    # Add WHERE at the end
                    query += f" WHERE {timestamp_field} > '{self.last_timestamp}'"
                    
            elif self.last_timestamp and 'WHERE' in query.upper():
                # Add AND condition to existing WHERE
                timestamp_field = self.field_mappings.get('timestamp', 'timestamp')
                query = query.replace('WHERE', f"WHERE {timestamp_field} > '{self.last_timestamp}' AND ")
                
            return query
    
    def _map_row_to_log(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a database row to a log entry.
        
        Args:
            row: A dictionary containing the database row
            
        Returns:
            Dict[str, Any]: A log entry
        """
        # Create a new log entry
        log = {}
        
        # Map all fields
        for log_field, db_field in self.field_mappings.items():
            if db_field in row:
                log[log_field] = row[db_field]
        
        # Ensure required fields exist
        if 'timestamp' not in log:
            log['timestamp'] = datetime.now().isoformat()
            
        if 'level' not in log:
            log['level'] = 'INFO'
            
        if 'message' not in log:
            # Try to create a message from available fields
            if 'message' in row:
                log['message'] = row['message']
            else:
                # Create a simple representation of the row
                log['message'] = f"Database log: {', '.join(f'{k}={v}' for k, v in row.items() if k not in ['timestamp', 'level', 'service'])}"
                
        if 'service' not in log:
            log['service'] = 'database'
            
        # Add metadata with all remaining fields
        metadata = {}
        for k, v in row.items():
            if k not in self.field_mappings.values():
                # Handle JSON strings in the database
                if isinstance(v, str) and (v.startswith('{') or v.startswith('[')):
                    try:
                        v = json.loads(v)
                    except:
                        pass
                metadata[k] = v
                
        if metadata:
            log['metadata'] = metadata
        else:
            log['metadata'] = {}
            
        # Convert any datetime objects to ISO strings
        for key, value in log.items():
            if isinstance(value, datetime):
                log[key] = value.isoformat()
                
        return log
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get logs from the database with optional filtering.
        
        Args:
            start_time: Optional start time to filter logs
            end_time: Optional end time to filter logs
            filters: Optional filters to apply
            limit: Optional limit of logs to return
            
        Returns:
            List[Dict[str, Any]]: A list of log entries
        """
        if start_time:
            self.last_timestamp = start_time.isoformat()
        
        return await self.fetch_logs()
    
    async def fetch_logs(self) -> List[Dict[str, Any]]:
        """
        Fetch logs from the database.
        
        Returns:
            List[Dict[str, Any]]: A list of log entries
        """
        if not self.connection:
            await self.connect()
            
        try:
            # Verify table exists and discover columns if it's a simple table name
            if ' ' not in self.log_query and ';' not in self.log_query:
                table_name = self.log_query
                
                # Get table columns to check if timestamp field exists
                columns = await self._get_table_columns(table_name)
                
                # If the specified timestamp field doesn't exist, try common timestamp column names
                timestamp_field = self.field_mappings.get('timestamp', 'timestamp')
                if timestamp_field not in columns:
                    # Try common timestamp column names
                    common_timestamp_fields = [
                        'created_at', 'timestamp', 'time', 'datetime', 'date', 'ts', 
                        'created', 'logged_at', 'event_time', 'log_time'
                    ]
                    
                    for field in common_timestamp_fields:
                        if field in columns:
                            # Update field mapping with the discovered timestamp field
                            self.field_mappings['timestamp'] = field
                            logger.info(f"Using discovered timestamp field: {field}")
                            break
            
            # Now build and execute query with the possibly updated field mappings
            query = self._build_query()
            logs = []
            
            if self.db_type == 'postgresql' or self.db_type == 'supabase' or self.db_type == 'neon':
                # Use asyncpg
                rows = await self.connection.fetch(query)
                for row in rows:
                    # Convert Record to dict
                    row_dict = dict(row.items())
                    logs.append(self._map_row_to_log(row_dict))
                    
            elif self.db_type == 'mysql':
                # Use aiomysql
                await self.cursor.execute(query)
                rows = await self.cursor.fetchall()
                for row in rows:
                    logs.append(self._map_row_to_log(row))
                    
            elif self.db_type == 'sqlite':
                # Use aiosqlite
                async with self.connection.execute(query) as cursor:
                    async for row in cursor:
                        logs.append(self._map_row_to_log(dict(row)))
                        
            # Sort by timestamp
            logs.sort(key=lambda x: x['timestamp'])
            
            return logs
            
        except Exception as e:
            logger.error(f"Error fetching logs from database: {str(e)}")
            raise
            
    async def _get_table_columns(self, table_name: str) -> List[str]:
        """
        Get the column names for a database table.
        
        Args:
            table_name: The name of the table
            
        Returns:
            List[str]: A list of column names
        """
        try:
            if self.db_type in ['postgresql', 'supabase', 'neon']:
                # PostgreSQL query for column names
                query = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}' AND table_schema = 'public'
                """
                columns = await self.connection.fetch(query)
                return [col['column_name'] for col in columns]
                
            elif self.db_type == 'mysql':
                # MySQL query for column names
                await self.cursor.execute(f"SHOW COLUMNS FROM {table_name}")
                columns = await self.cursor.fetchall()
                return [col['Field'] for col in columns]
                
            elif self.db_type == 'sqlite':
                # SQLite query for column names
                async with self.connection.execute(f"PRAGMA table_info({table_name})") as cursor:
                    columns = []
                    async for row in cursor:
                        columns.append(row[1])  # Column name is at index 1
                    return columns
                    
            return []
                
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {str(e)}")
            return []
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream logs from the database.
        
        Args:
            from_timestamp: Optional timestamp to start from
            
        Yields:
            Dict[str, Any]: Log entries
        """
        try:
            if from_timestamp:
                self.last_timestamp = from_timestamp.isoformat()
                
            logs = await self.fetch_logs()
            
            for log in logs:
                yield log
                
        finally:
            await self.disconnect()
    
    async def discover_tables(self) -> List[str]:
        """
        Discover available tables in the database that could contain logs.
        
        Returns:
            List[str]: A list of table names
        """
        if not self.connection:
            await self.connect()
            
        try:
            if self.db_type in ['postgresql', 'supabase', 'neon']:
                # Query to list tables in PostgreSQL/Supabase/Neon
                query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
                """
                tables = await self.connection.fetch(query)
                return [table['table_name'] for table in tables]
                
            elif self.db_type == 'mysql':
                # Query to list tables in MySQL
                await self.cursor.execute("SHOW TABLES")
                tables = await self.cursor.fetchall()
                return [list(table.values())[0] for table in tables]
                
            elif self.db_type == 'sqlite':
                # Query to list tables in SQLite
                async with self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                    tables = []
                    async for row in cursor:
                        tables.append(row[0])
                    return tables
            
            return []
                
        except Exception as e:
            logger.error(f"Error discovering tables: {str(e)}")
            return []