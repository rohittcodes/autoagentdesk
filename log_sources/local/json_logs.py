import json
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from . import LocalFileLogSource

class JSONLogSource(LocalFileLogSource):
    """Implementation for reading JSON log files"""
    
    def _validate_config(self) -> None:
        """Validate configuration for JSON log source"""
        super()._validate_config()
        
        # Validate field mappings if provided, otherwise use defaults
        self.field_mappings = self.config.get("field_mappings", {
            "timestamp": ["timestamp", "time", "@timestamp"],
            "level": ["level", "severity", "log_level"],
            "message": ["message", "msg", "log"],
        })
        
        # Validate timestamp format if provided
        self.timestamp_format = self.config.get("timestamp_format")
    
    def _extract_field(self, data: Dict[str, Any], field_names: List[str]) -> Optional[str]:
        """Extract a field value using multiple possible field names"""
        for name in field_names:
            if name in data:
                return data[name]
        return None
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object"""
        if not timestamp_str:
            return datetime.utcnow()
            
        try:
            if self.timestamp_format:
                return datetime.strptime(timestamp_str, self.timestamp_format)
            
            # Try common formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds
                "%Y-%m-%dT%H:%M:%SZ",      # ISO format
                "%Y-%m-%d %H:%M:%S.%f",    # With microseconds
                "%Y-%m-%d %H:%M:%S",       # Basic format
            ]:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
                    
            # If all parsing attempts fail, try float/int timestamp
            return datetime.fromtimestamp(float(timestamp_str))
            
        except (ValueError, TypeError):
            return datetime.utcnow()
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream logs from JSON file"""
        if not self.file_handle:
            await self.connect()
        
        for line in self.file_handle:
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # If line isn't valid JSON, yield it as raw message
                yield {
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": line,
                    "level": "UNKNOWN"
                }
                continue
            
            # Extract fields using mappings
            timestamp_str = self._extract_field(data, self.field_mappings["timestamp"])
            timestamp = self._parse_timestamp(timestamp_str)
            
            # Skip if before from_timestamp
            if from_timestamp and timestamp < from_timestamp:
                continue
            
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "level": self._extract_field(data, self.field_mappings["level"]) or "INFO",
                "message": self._extract_field(data, self.field_mappings["message"]) or str(data),
                "raw": data  # Include raw data for access to all fields
            }
            
            yield log_entry
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get logs from JSON file with filtering"""
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
                    # Check in both top-level fields and raw data
                    if key in log and log[key] != value:
                        if key in log["raw"] and log["raw"][key] != value:
                            match = False
                            break
                if not match:
                    continue
            
            logs.append(log)
            count += 1
            
            if limit and count >= limit:
                break
        
        return logs