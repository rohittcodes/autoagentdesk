from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime

class LogSource(ABC):
    """Base class for all log sources"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate the configuration for this log source"""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the log source"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the log source"""
        pass
    
    @abstractmethod
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream logs from the source"""
        pass

    @abstractmethod
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get logs from the source with optional filtering"""
        pass