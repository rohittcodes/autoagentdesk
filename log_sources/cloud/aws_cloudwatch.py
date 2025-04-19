from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime, timezone
import aioboto3
from .. import LogSource

class CloudWatchLogSource(LogSource):
    """AWS CloudWatch Logs source implementation"""
    
    def _validate_config(self) -> None:
        required_fields = [
            "aws_access_key_id",
            "aws_secret_access_key",
            "region_name",
            "log_group_name"
        ]
        missing_fields = [field for field in required_fields if field not in self.config]
        if missing_fields:
            raise ValueError(f"Missing required AWS CloudWatch fields: {', '.join(missing_fields)}")
    
    async def connect(self) -> None:
        self.session = aioboto3.Session(
            aws_access_key_id=self.config["aws_access_key_id"],
            aws_secret_access_key=self.config["aws_secret_access_key"],
            region_name=self.config["region_name"]
        )
        self.client = await self.session.client('logs').__aenter__()
    
    async def disconnect(self) -> None:
        if hasattr(self, 'client'):
            await self.client.__aexit__(None, None, None)
    
    async def stream_logs(self, from_timestamp: Optional[datetime] = None) -> AsyncGenerator[Dict[str, Any], None]:
        if not hasattr(self, 'client'):
            await self.connect()
        
        kwargs = {
            'logGroupName': self.config["log_group_name"],
            'startFromHead': True
        }
        
        if from_timestamp:
            kwargs['startTime'] = int(from_timestamp.timestamp() * 1000)
        
        # Get log streams
        streams_response = await self.client.describe_log_streams(**kwargs)
        
        for stream in streams_response['logStreams']:
            kwargs = {
                'logGroupName': self.config["log_group_name"],
                'logStreamName': stream['logStreamName'],
            }
            
            if from_timestamp:
                kwargs['startTime'] = int(from_timestamp.timestamp() * 1000)
            
            while True:
                response = await self.client.get_log_events(**kwargs)
                
                for event in response['events']:
                    yield {
                        'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000, tz=timezone.utc),
                        'message': event['message'],
                        'stream': stream['logStreamName']
                    }
                
                # Handle pagination
                if response['nextForwardToken'] == kwargs.get('nextToken'):
                    break
                    
                kwargs['nextToken'] = response['nextForwardToken']
    
    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not hasattr(self, 'client'):
            await self.connect()
        
        kwargs = {
            'logGroupName': self.config["log_group_name"],
        }
        
        if start_time:
            kwargs['startTime'] = int(start_time.timestamp() * 1000)
        if end_time:
            kwargs['endTime'] = int(end_time.timestamp() * 1000)
            
        # Convert filters to CloudWatch Logs filter pattern
        if filters:
            filter_pattern = " ".join([f'{k}={v}' for k, v in filters.items()])
            kwargs['filterPattern'] = filter_pattern
            
        if limit:
            kwargs['limit'] = limit
        
        response = await self.client.filter_log_events(**kwargs)
        
        logs = []
        for event in response['events']:
            logs.append({
                'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000, tz=timezone.utc),
                'message': event['message'],
                'stream': event['logStreamName']
            })
            
        return logs