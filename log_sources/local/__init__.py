from typing import Dict, Any, Optional
from pathlib import Path
from .. import LogSource

class LocalFileLogSource(LogSource):
    """Base class for local file log sources"""
    
    def __init__(self, config: Dict[str, Any]):
        self.file_handle = None
        super().__init__(config)
    
    def _validate_config(self) -> None:
        """Validate the configuration for local file log source"""
        if "file_path" not in self.config:
            raise ValueError("Missing required field: file_path (path to log file)")
        
        file_path = Path(self.config["file_path"])
        if not file_path.exists():
            raise ValueError(f"Log file does not exist: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
    
    async def connect(self) -> None:
        """Open the file for reading"""
        self.file_handle = open(self.config["file_path"], "r")
    
    async def disconnect(self) -> None:
        """Close the file handle"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None