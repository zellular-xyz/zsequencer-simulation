import asyncio
import json
import time
from uuid import uuid4

import aiohttp


class BatchSender:
    REQUESTS_PER_SECOND = 150
    BATCH_SIZE = 3

    def __init__(self, logger, app_name):
        self.app_name = app_name
        self._node_sockets = None
        self.logger = logger
        self.shutdown_event = asyncio.Event()

    def set_node_sockets(self, node_sockets):
        self._node_sockets = node_sockets

    async def send_batch_to_node(self, session: aiohttp.ClientSession, node_url: str):
        try:
            t = int(time.time())
            batch = [{"tx_id": str(uuid4()), "operation": "foo", "t": t} for _ in range(self.BATCH_SIZE)]
            string_data = json.dumps(batch)

            start_time = time.perf_counter()
            async with session.put(
                    url=f"{node_url}/node/{self.app_name}/batches",
                    data=string_data,
                    headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    end_time = time.perf_counter()
                    execution_time_ns = (end_time - start_time) * 1_000_000_000
                    self.logger.log(f"Execution time of client: {execution_time_ns:.0f} ns")
                    print(f"Batch sent successfully to {node_url} at {time.ctime()}")
                else:
                    print(f"Failed to send batch to {node_url} with status code {response.status}")
        except Exception as error:
            print(f"Error sending batch to {node_url}: {error}")

    async def send_batches_concurrently(self):
        async with aiohttp.ClientSession() as session:
            while not self.shutdown_event.is_set():
                start_time = time.perf_counter()

                tasks = [
                    self.send_batch_to_node(session, node_url)
                    for node_url in self._node_sockets
                    for _ in range(self.REQUESTS_PER_SECOND)
                ]

                # Run all tasks concurrently
                await asyncio.gather(*tasks)

                end_time = time.perf_counter()

                time_to_wait = max(0, 1 - (end_time - start_time))
                await asyncio.sleep(time_to_wait)
