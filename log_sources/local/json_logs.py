import json
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from . import LocalFileLogSource
import re

class JSONLogSource(LocalFileLogSource):
    """Implementation for reading JSON log files"""
    
    def _validate_config(self) -> None:
        """Validate configuration for JSON log source"""
        super()._validate_config()
        
        # Validate field mappings if provided, otherwise use defaults that match our log format
        self.field_mappings = self.config.get("field_mappings", {
            "timestamp": ["timestamp", "time", "@timestamp"],
            "level": ["level", "severity", "log_level"],
            "message": ["message", "msg", "log", "content"],
            "service": ["service", "source", "application", "app"],
            "producer_id": ["producer_id", "producer", "source_id", "id"],
            "metadata": ["metadata", "meta", "attributes", "context"]
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
        """Stream logs from JSON file with enhanced field detection"""
        if not self.file_handle:
            await self.connect()
        
        # Try to determine if the file is a JSON array first
        try:
            self.file_handle.seek(0)
            first_char = self.file_handle.read(1).strip()
            self.file_handle.seek(0)
            
            if first_char == '[':
                # File may be a JSON array rather than line-delimited JSON
                content = self.file_handle.read()
                data = json.loads(content)
                
                if isinstance(data, list):
                    for item in data:
                        # Enhanced field extraction with smart defaults
                        timestamp_str = self._extract_field(item, self.field_mappings["timestamp"])
                        timestamp = self._parse_timestamp(timestamp_str) if timestamp_str else datetime.utcnow()
                        
                        # Skip if before from_timestamp
                        if from_timestamp and timestamp < from_timestamp:
                            continue
                        
                        # Generate meaningful defaults based on content
                        level = self._extract_field(item, self.field_mappings["level"])
                        if not level:
                            # Infer log level from content if possible
                            message = str(self._extract_field(item, self.field_mappings["message"]) or "")
                            if "error" in message.lower() or "fail" in message.lower() or "exception" in message.lower():
                                level = "ERROR"
                            elif "warn" in message.lower():
                                level = "WARN"
                            elif "debug" in message.lower():
                                level = "DEBUG"
                            else:
                                level = "INFO"
                        
                        service = self._extract_field(item, self.field_mappings["service"])
                        if not service:
                            # Try to infer from other fields
                            if "service_name" in item:
                                service = item["service_name"]
                            elif "app_name" in item:
                                service = item["app_name"]
                            elif "component" in item:
                                service = item["component"]
                            else:
                                # Extract from log content if possible
                                message = str(self._extract_field(item, self.field_mappings["message"]) or "")
                                service_match = re.search(r"service[:\s]+([a-zA-Z0-9-_]+)", message, re.IGNORECASE)
                                if service_match:
                                    service = service_match.group(1)
                                else:
                                    service = self._infer_service_from_content(item)
                        
                        producer_id = self._extract_field(item, self.field_mappings["producer_id"])
                        if not producer_id:
                            # Try to extract from other fields
                            if "host" in item:
                                producer_id = item["host"]
                            elif "hostname" in item:
                                producer_id = item["hostname"]
                            elif "instance_id" in item:
                                producer_id = item["instance_id"]
                            else:
                                producer_id = f"host-{hash(str(timestamp)) % 1000:03d}"
                        
                        # Use all remaining fields as metadata if metadata is not found
                        metadata = self._extract_field(item, self.field_mappings["metadata"])
                        if not metadata:
                            # Get all fields that aren't already extracted
                            metadata = {k: v for k, v in item.items() 
                                      if k not in self.field_mappings["timestamp"] and
                                         k not in self.field_mappings["level"] and
                                         k not in self.field_mappings["message"] and
                                         k not in self.field_mappings["service"] and
                                         k not in self.field_mappings["producer_id"]}
                        
                        log_entry = {
                            "timestamp": timestamp.isoformat(),
                            "level": level,
                            "message": self._extract_field(item, self.field_mappings["message"]) or self._generate_summary(item),
                            "service": service,
                            "producer_id": producer_id,
                            "metadata": metadata or {},
                            "raw": item
                        }
                        
                        yield log_entry
                    return
        except Exception as e:
            # If it fails, reset file position and continue with line-by-line processing
            self.file_handle.seek(0)
        
        # Process as line-delimited JSON (JSONL/NDJSON format)
        for line in self.file_handle:
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Process raw text line for better defaults
                yield self._process_raw_text_line(line)
                continue
            
            # Extract fields using mappings with smart defaults
            timestamp_str = self._extract_field(data, self.field_mappings["timestamp"])
            timestamp = self._parse_timestamp(timestamp_str) if timestamp_str else datetime.utcnow()
            
            # Skip if before from_timestamp
            if from_timestamp and timestamp < from_timestamp:
                continue
            
            # Apply the same smart field extraction as above
            level = self._extract_field(data, self.field_mappings["level"])
            if not level:
                message = str(self._extract_field(data, self.field_mappings["message"]) or "")
                if "error" in message.lower() or "fail" in message.lower() or "exception" in message.lower():
                    level = "ERROR"
                elif "warn" in message.lower():
                    level = "WARN"
                elif "debug" in message.lower():
                    level = "DEBUG"
                else:
                    level = "INFO"
            
            service = self._extract_field(data, self.field_mappings["service"])
            if not service:
                if "service_name" in data:
                    service = data["service_name"]
                elif "app_name" in data:
                    service = data["app_name"]
                elif "component" in data:
                    service = data["component"]
                else:
                    message = str(self._extract_field(data, self.field_mappings["message"]) or "")
                    service_match = re.search(r"service[:\s]+([a-zA-Z0-9-_]+)", message, re.IGNORECASE)
                    if service_match:
                        service = service_match.group(1)
                    else:
                        service = self._infer_service_from_content(data)
            
            producer_id = self._extract_field(data, self.field_mappings["producer_id"])
            if not producer_id:
                if "host" in data:
                    producer_id = data["host"]
                elif "hostname" in data:
                    producer_id = data["hostname"]
                elif "instance_id" in data:
                    producer_id = data["instance_id"]
                else:
                    producer_id = f"host-{hash(str(timestamp)) % 1000:03d}"
            
            metadata = self._extract_field(data, self.field_mappings["metadata"])
            if not metadata:
                metadata = {k: v for k, v in data.items() 
                          if k not in self.field_mappings["timestamp"] and
                             k not in self.field_mappings["level"] and
                             k not in self.field_mappings["message"] and
                             k not in self.field_mappings["service"] and
                             k not in self.field_mappings["producer_id"]}
            
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "level": level,
                "message": self._extract_field(data, self.field_mappings["message"]) or self._generate_summary(data),
                "service": service,
                "producer_id": producer_id,
                "metadata": metadata or {},
                "raw": data
            }
            
            yield log_entry

    def _process_raw_text_line(self, line: str) -> Dict[str, Any]:
        """Process a raw text line that failed JSON parsing"""
        # Try to extract timestamp
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)', line)
        timestamp = datetime.utcnow()
        if timestamp_match:
            try:
                timestamp = self._parse_timestamp(timestamp_match.group(1))
            except (ValueError, TypeError):
                pass
        
        # Try to extract log level
        level_match = re.search(r'\b(ERROR|INFO|WARN(?:ING)?|DEBUG|CRITICAL|FATAL)\b', line, re.IGNORECASE)
        level = "INFO"
        if level_match:
            level_text = level_match.group(1).upper()
            if level_text.startswith("WARN"):
                level = "WARN"
            elif level_text in ("CRITICAL", "FATAL"):
                level = "ERROR"
            else:
                level = level_text
        elif "error" in line.lower() or "exception" in line.lower() or "fail" in line.lower():
            level = "ERROR"
        
        # Try to extract service
        service_match = re.search(r'\b([a-zA-Z0-9_-]+(?:[-_][a-zA-Z0-9]+)*)[:/]', line)
        service = "app"
        if service_match:
            service = service_match.group(1)
        
        return {
            "timestamp": timestamp.isoformat(),
            "level": level,
            "message": line,
            "service": service,
            "producer_id": f"log-parser",
            "metadata": {}
        }

    def _infer_service_from_content(self, data: Dict[str, Any]) -> str:
        """Infer service name from log content"""
        # Check common patterns for service names
        message = str(self._extract_field(data, self.field_mappings["message"]) or "")
        
        # Check for prefixes that might indicate services
        patterns = [
            r'\[([a-zA-Z0-9_-]+)\]',  # [service-name]
            r'\"service\":\"([^\"]+)\"',  # "service":"name"
            r'@([a-zA-Z0-9_-]+)',  # @service-name
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        
        # Fallback to data keys
        keys_str = "-".join(sorted(data.keys()))
        return f"service-{hash(keys_str) % 1000:03d}"

    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate a summary message from data when no message field exists"""
        # Create a meaningful message from available data
        parts = []
        
        # Add key fields if they exist
        important_fields = ["action", "event", "operation", "request", "response", "status", "error", "result"]
        for field in important_fields:
            if field in data:
                parts.append(f"{field}: {data[field]}")
        
        # If we have parts, use them
        if parts:
            return " | ".join(parts)
        
        # Fallback to a summary of the data
        fields = list(data.keys())
        if len(fields) > 3:
            field_summary = ", ".join(fields[:3]) + f" and {len(fields)-3} more fields"
        else:
            field_summary = ", ".join(fields)
        
        return f"Log entry with fields: {field_summary}"

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