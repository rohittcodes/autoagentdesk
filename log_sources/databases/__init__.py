from typing import Any, Dict, Optional
from ..import LogSource

class DatabaseLogSource(LogSource):
    """Base class for database log sources"""
    
    def __init__(self, config: Dict[str, Any]):
        self.connection = None
        super().__init__(config)
    
    def _validate_config(self) -> None:
        required_fields = ["host", "port", "database", "table"]
        missing_fields = [field for field in required_fields if field not in self.config]
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
    
    async def disconnect(self) -> None:
        if self.connection:
            await self.connection.close()
            self.connection = None