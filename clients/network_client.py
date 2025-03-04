import asyncio
import logging
import time
from typing import List, Tuple
from clients.node_client import NodeClient


class NetworkClient:
    def __init__(self, targets: List[Tuple[str, int]], requests_per_second=10, concurrent_requests=1):
        """
        Initialize NetworkClient with a list of (host, port) targets.

        Args:
            targets: List of tuples containing (host, port)
            requests_per_second: Requests per second for each node
            concurrent_requests: Concurrent requests allowed per node
        """
        self.logger = logging.getLogger("NetworkClient")
        self.clients = [
            NodeClient(
                host=host,
                port=port,
                requests_per_second=requests_per_second,
                concurrent_requests=concurrent_requests
            ) for host, port in targets
        ]
        self.start_time = None

    async def run(self):
        """Run all NodeClients concurrently."""
        self.start_time = time.time()
        self.logger.info(f"Starting NetworkClient with {len(self.clients)} nodes")

        try:
            tasks = [client.run() for client in self.clients]
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            end_time = time.time()
            duration = end_time - self.start_time
            total_attempts = sum(client.results.count(None) + len(client.results) for client in self.clients)
            total_successful = sum(len(client.results) for client in self.clients)

            self.logger.info(f"Network stopped after {duration:.2f} seconds")
            self.logger.info(f"Total attempts across all nodes: {total_attempts}")
            self.logger.info(f"Total successful requests across all nodes: {total_successful}")
            if duration > 0:
                self.logger.info(f"Network average successful RPS: {total_successful / duration:.2f}")

    def start(self):
        """Public method to start the network client."""
        asyncio.run(self.run())


if __name__ == "__main__":
    # Example usage with multiple targets, some might be down
    targets = [
        ("localhost", 6001),  # Assume this is up
        ("localhost", 6002),  # Assume this is down
        ("localhost", 6003)  # Assume this is up
    ]

    network = NetworkClient(
        targets=targets,
        requests_per_second=10,
        concurrent_requests=2
    )
    network.start()
