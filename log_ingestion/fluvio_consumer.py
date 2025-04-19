import json
import asyncio
from fluvio import Fluvio
from datetime import datetime

class LogConsumer:
    def __init__(self, topic_name, batch_processor, max_batch_size=100, processing_interval=5):
        self.fluvio = Fluvio.connect()
        self.topic_name = topic_name
        self.consumer = self.fluvio.partition_consumer(topic_name, 0)
        self.batch_processor = batch_processor
        self.max_batch_size = max_batch_size
        self.processing_interval = processing_interval
        self.buffer = []
        self.running = False
    
    async def start_consuming(self):
        """Start consuming logs from Fluvio"""
        self.running = True
        await self.consumer.seek_to_end()
        
        # Start background batch processor
        asyncio.create_task(self._process_batches())
        
        while self.running:
            try:
                record = await self.consumer.next()
                if record and record.value():
                    log_entry = json.loads(record.value_string())
                    self.buffer.append(log_entry)
                    
                    # Process immediately if buffer reaches max size
                    if len(self.buffer) >= self.max_batch_size:
                        await self._process_current_batch()
            except Exception as e:
                print(f"Error consuming log: {e}")
                await asyncio.sleep(1)
    
    async def _process_batches(self):
        """Periodically process batches of logs"""
        while self.running:
            await asyncio.sleep(self.processing_interval)
            if self.buffer:
                await self._process_current_batch()
    
    async def _process_current_batch(self):
        """Process the current batch of logs"""
        if not self.buffer:
            return
            
        batch = self.buffer.copy()
        self.buffer = []

         # Send the batch to the processor
        try:
            await self.batch_processor(batch)
        except Exception as e:
            print(f"Error processing batch: {e}")
            # Could implement retry logic here
    
    async def stop(self):
        """Stop the consumer"""
        self.running = False
        # Process any remaining logs before stopping
        if self.buffer:
            await self._process_current_batch()