import re
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator, Pattern
from . import LocalFileLogSource

class TextLogSource(LocalFileLogSource):
    """Implementation for reading plain text log files"""
    
    def __init__(self, config: Dict[str, Any]):
        self.pattern: Optional[Pattern] = None
        super().__init__(config)
    
    def _validate_config(self) -> None:
        """Validate configuration for text log source"""
        super()._validate_config()
        
        # Validate log pattern if provided
        if "pattern" in self.config:
            try:
                self.pattern = re.compile(self.config["pattern"])
            except re.error as e:
                raise ValueError(f"Invalid log pattern: {str(e)}")
        else:
            # Default pattern matches common log formats
            # Example: 2024-04-19 10:30:45 [INFO] Message here
            self.pattern = re.compile(
                r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
                r"\s*"
                r"(?:\[(?P<level>\w+)\])?"
                r"\s*"
                r"(?P<message>.*)"
            )
        
        # Validate timestamp format if provided
        self.timestamp_format = self.config.get(
            "timestamp_format", 
            "%Y-%m-%d %H:%M:%S"
        )
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream logs from text file"""
        if not self.file_handle:
            await self.connect()
        
        for line in self.file_handle:
            line = line.strip()
            if not line:
                continue
                
            match = self.pattern.match(line)
            if not match:
                # If line doesn't match pattern, yield it as raw message
                yield {
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": line,
                    "level": "UNKNOWN",
                    "service": "text-log",
                    "producer_id": "file",
                    "metadata": {}
                }
                continue
            
            data = match.groupdict()
            
            # Parse timestamp
            try:
                timestamp = datetime.strptime(
                    data["timestamp"],
                    self.timestamp_format
                )
            except (ValueError, KeyError):
                timestamp = datetime.utcnow()
            
            # Skip if before from_timestamp
            if from_timestamp and timestamp < from_timestamp:
                continue
            
            yield {
                "timestamp": timestamp.isoformat(),
                "level": data.get("level", "INFO"),
                "message": data.get("message", line),
                "service": "text-log",
                "producer_id": "file",
                "metadata": {}
            }
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get logs from text file with filtering"""
        if not self.file_handle:
            await self.connect()
        
        logs = []
        count = 0
        
        async for log in self.stream_logs(start_time):
            # Apply time range filter
            if end_time:
                log_time = datetime.fromisoformat(log["timestamp"])
                if log_time > end_time:
                    continue
            
            # Apply other filters
            if filters:
                match = True
                for key, value in filters.items():
                    if key in log and log[key] != value:
                        match = False
                        break
                if not match:
                    continue
            
            logs.append(log)
            count += 1
            
            if limit and count >= limit:
                break
        
        return logs