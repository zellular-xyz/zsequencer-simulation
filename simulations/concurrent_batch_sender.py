import asyncio
import json
import time
from uuid import uuid4

import aiohttp


class BatchSender:
    def __init__(self, logger, app_name):
        """
        Initializes the BatchSender.

        :param logger: Logger for general logs.
        """
        self.app_name = app_name
        self._node_sockets = None
        self.logger = logger
        self.shutdown_event = asyncio.Event()

    def set_node_sockets(self, node_sockets):
        self._node_sockets = node_sockets

    async def send_batch_to_node(self, session: aiohttp.ClientSession, node_url: str):
        """
        Sends a single batch of transactions to a specific node using aiohttp.
        """

        try:
            t = int(time.time())
            batch = [{"tx_id": str(uuid4()), "operation": "foo", "t": t} for _ in range(20)]
            string_data = json.dumps(batch)

            async with session.put(
                    url=f"{node_url}/node/{self.app_name}/batches",
                    data=string_data,
                    headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    print(f"Batch sent successfully to {node_url} at {time.ctime()}")
                else:
                    print(f"Failed to send batch to {node_url} with status code {response.status}")
        except Exception as error:
            print(f"Error sending batch to {node_url}: {error}")

    async def send_batch(self, session: aiohttp.ClientSession):
        """
        Sends a single batch to all nodes in the node_sockets list.
        """
        tasks = [
            self.send_batch_to_node(session, node_url)
            for node_url in self._node_sockets
        ]
        await asyncio.gather(*tasks)

    async def send_batches_concurrently(self):
        """
        Continuously sends batches of transactions concurrently
        to all nodes and logs the time gap for each round.
        """
        requests_per_second = 1000

        async with aiohttp.ClientSession() as session:
            while not self.shutdown_event.is_set():
                start_time = time.time()

                # Create tasks for this round
                tasks = [
                    self.send_batch(session)
                    for _ in range(requests_per_second)
                ]

                # Run all tasks concurrently
                await asyncio.gather(*tasks)

                # Calculate the gap time
                end_time = time.time()
                gap_time = end_time - start_time
                self.logger.log(f"Round completed. Time gap: {gap_time:.2f} seconds")

                # Pause for the next round
                await asyncio.sleep(1)
