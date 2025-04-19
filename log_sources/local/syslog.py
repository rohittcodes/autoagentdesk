import re
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator, Pattern
from . import LocalFileLogSource

class SyslogSource(LocalFileLogSource):
    """Implementation for reading syslog format logs"""
    
    def __init__(self, config: Dict[str, Any]):
        self.rfc5424_pattern: Pattern
        self.legacy_pattern: Pattern
        super().__init__(config)
    
    def _validate_config(self) -> None:
        """Validate configuration for syslog source"""
        super()._validate_config()
        
        # RFC5424 format
        # <priority>version timestamp hostname app-name procid msgid structured-data msg
        self.rfc5424_pattern = re.compile(
            r"<(?P<pri>\d+)>(?P<version>\d+) (?P<timestamp>[-\d]+T[:.:\d]+(?:Z|[-+]\d{2}:?\d{2})?)"
            r" (?P<hostname>[-\w]+) (?P<app>\S+) (?P<procid>\S+) (?P<msgid>\S+)"
            r" (?P<sd>(?:\[.*?\])*|-)"
            r"(?: (?P<message>.+))?$"
        )
        
        # Legacy syslog format
        # timestamp hostname app[pid]: message
        self.legacy_pattern = re.compile(
            r"(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
            r" (?P<hostname>[-\w]+)"
            r" (?P<app>\S+?)(?:\[(?P<pid>\d+)\])?:"
            r" (?P<message>.+)$"
        )
        
        self.facility_map = {
            0: "kern",
            1: "user",
            2: "mail",
            3: "daemon",
            4: "auth",
            5: "syslog",
            6: "lpr",
            7: "news",
            8: "uucp",
            9: "cron",
            10: "authpriv",
            11: "ftp",
            12: "ntp",
            13: "security",
            14: "console",
            15: "mark",
        }
        
        self.severity_map = {
            0: "EMERG",
            1: "ALERT",
            2: "CRIT",
            3: "ERR",
            4: "WARNING",
            5: "NOTICE",
            6: "INFO",
            7: "DEBUG",
        }
    
    def _parse_priority(self, pri: str) -> Dict[str, str]:
        """Parse syslog priority value into facility and severity"""
        try:
            pri_num = int(pri)
            facility_num = pri_num >> 3
            severity_num = pri_num & 0x07
            
            return {
                "facility": self.facility_map.get(facility_num, "unknown"),
                "severity": self.severity_map.get(severity_num, "UNKNOWN"),
            }
        except (ValueError, TypeError):
            return {
                "facility": "unknown",
                "severity": "UNKNOWN",
            }
    
    def _parse_structured_data(self, sd: str) -> Dict[str, Any]:
        """Parse RFC5424 structured data"""
        if not sd or sd == "-":
            return {}
            
        result = {}
        # Match [id key="value" ...]
        sd_pattern = re.compile(r'\[([^]]+)\]')
        for match in sd_pattern.finditer(sd):
            elements = match.group(1).split(' ', 1)
            if len(elements) > 1:
                sd_id = elements[0]
                # Match key="value"
                params = dict(re.findall(r'(\S+)="([^"]*)"', elements[1]))
                result[sd_id] = params
        return result
    
    def _parse_legacy_timestamp(self, timestamp: str) -> datetime:
        """Parse legacy syslog timestamp"""
        current_year = datetime.now().year
        try:
            # Add current year since legacy format doesn't include it
            full_timestamp = f"{timestamp} {current_year}"
            return datetime.strptime(full_timestamp, "%b %d %H:%M:%S %Y")
        except ValueError:
            return datetime.utcnow()
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream logs from syslog file"""
        if not self.file_handle:
            await self.connect()
        
        for line in self.file_handle:
            line = line.strip()
            if not line:
                continue
            
            # Try RFC5424 format first
            match = self.rfc5424_pattern.match(line)
            if match:
                data = match.groupdict()
                pri_info = self._parse_priority(data["pri"])
                
                try:
                    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                except ValueError:
                    timestamp = datetime.utcnow()
                
                # Skip if before from_timestamp
                if from_timestamp and timestamp < from_timestamp:
                    continue
                
                yield {
                    "timestamp": timestamp.isoformat(),
                    "hostname": data["hostname"],
                    "app": data["app"],
                    "procid": data["procid"],
                    "msgid": data["msgid"],
                    "facility": pri_info["facility"],
                    "level": pri_info["severity"],
                    "message": data.get("message", ""),
                    "structured_data": self._parse_structured_data(data["sd"]),
                }
                continue
            
            # Try legacy format
            match = self.legacy_pattern.match(line)
            if match:
                data = match.groupdict()
                timestamp = self._parse_legacy_timestamp(data["timestamp"])
                
                # Skip if before from_timestamp
                if from_timestamp and timestamp < from_timestamp:
                    continue
                
                yield {
                    "timestamp": timestamp.isoformat(),
                    "hostname": data["hostname"],
                    "app": data["app"],
                    "pid": data.get("pid"),
                    "level": "INFO",  # Legacy format doesn't include severity
                    "facility": "user",  # Default facility
                    "message": data["message"],
                }
                continue
            
            # If no match, yield as raw message
            yield {
                "timestamp": datetime.utcnow().isoformat(),
                "message": line,
                "level": "UNKNOWN",
            }
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get logs from syslog file with filtering"""
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