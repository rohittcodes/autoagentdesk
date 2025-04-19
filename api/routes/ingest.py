from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Dict, Any, Optional
from enum import Enum
from pathlib import Path
import os
import tempfile

from storage.chroma_client import ChromaLogStore
from log_sources.local.text import TextLogSource
from log_sources.local.json_logs import JSONLogSource
from log_sources.local.syslog import SyslogSource

router = APIRouter(prefix="/ingest", tags=["ingest"])

class LogFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    SYSLOG = "syslog"

async def get_log_store():
    from config import CHROMA_DB_PATH, LOG_RETENTION_DAYS, GOOGLE_API_KEY
    return ChromaLogStore(CHROMA_DB_PATH, google_api_key=GOOGLE_API_KEY, retention_days=LOG_RETENTION_DAYS)

@router.post("/file")
async def ingest_log_file(
    file: UploadFile = File(...),
    format: LogFormat = Form(...),
    pattern: Optional[str] = Form(None),
    timestamp_format: Optional[str] = Form(None),
    field_mappings: Optional[Dict[str, Any]] = Form(None),
    log_store: ChromaLogStore = Depends(get_log_store)
):
    """Ingest logs from an uploaded file"""
    try:
        # Create a temporary file to store the upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Configure the appropriate log source based on format
            config = {"file_path": temp_path}
            if pattern:
                config["pattern"] = pattern
            if timestamp_format:
                config["timestamp_format"] = timestamp_format
            if field_mappings:
                config["field_mappings"] = field_mappings

            # Create the appropriate log source
            if format == LogFormat.TEXT:
                source = TextLogSource(config)
            elif format == LogFormat.JSON:
                source = JSONLogSource(config)
            else:  # SYSLOG
                source = SyslogSource(config)

            # Read and store logs
            logs = []
            async for log in source.stream_logs():
                logs.append(log)

            # Store logs in ChromaDB
            if logs:
                await log_store.store_logs(logs)

            return {
                "message": f"Successfully ingested {len(logs)} logs",
                "format": format,
                "filename": file.filename
            }

        finally:
            # Clean up the temporary file
            os.unlink(temp_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting log file: {str(e)}")

@router.post("/directory")
async def ingest_log_directory(
    directory: str,
    format: LogFormat,
    pattern: Optional[str] = None,
    timestamp_format: Optional[str] = None,
    field_mappings: Optional[Dict[str, Any]] = None,
    recursive: bool = False,
    log_store: ChromaLogStore = Depends(get_log_store)
):
    """Ingest logs from a directory on the server"""
    try:
        path = Path(directory)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")
        if not path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {directory}")

        total_logs = 0
        failed_files = []

        # Build basic config
        base_config = {}
        if pattern:
            base_config["pattern"] = pattern
        if timestamp_format:
            base_config["timestamp_format"] = timestamp_format
        if field_mappings:
            base_config["field_mappings"] = field_mappings

        # Process each file
        for file_path in path.rglob("*") if recursive else path.glob("*"):
            if not file_path.is_file():
                continue

            try:
                config = {**base_config, "file_path": str(file_path)}

                # Create appropriate source
                if format == LogFormat.TEXT:
                    source = TextLogSource(config)
                elif format == LogFormat.JSON:
                    source = JSONLogSource(config)
                else:  # SYSLOG
                    source = SyslogSource(config)

                # Read and store logs
                logs = []
                async for log in source.stream_logs():
                    logs.append(log)

                if logs:
                    await log_store.store_logs(logs)
                    total_logs += len(logs)

            except Exception as e:
                failed_files.append({"file": str(file_path), "error": str(e)})

        return {
            "message": f"Successfully ingested {total_logs} logs",
            "format": format,
            "directory": directory,
            "failed_files": failed_files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting log directory: {str(e)}")