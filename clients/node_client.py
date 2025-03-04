import asyncio
import logging
import random
import string
import time
import aiohttp

# Configure logging once at the module level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()  # Get root logger
if not logger.handlers:  # Add handler only if not already present
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)


class NodeClient:
    def __init__(self, host='localhost', port=6003, requests_per_second=10, concurrent_requests=1):
        """Initialize NodeClient with host, port, and request rate parameters."""
        self.logger = logging.getLogger(f"NodeClient_{host}:{port}")
        self.host = host
        self.port = port
        self.requests_per_second = requests_per_second
        self.concurrent_requests = concurrent_requests
        self.url = f"http://{self.host}:{self.port}/node/batches"
        self.results = []
        self.start_time = None
        self.is_down = False  # Track if node is currently down

    def generate_random_string(self, length=10):
        """Generate a random alphanumeric string of given length."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    async def send_batch(self, session, semaphore):
        """Send a batch (POST request) to the server with form data, handle connection errors."""
        async with semaphore:
            batch_data = {
                'simple_app': [self.generate_random_string() for _ in range(10)]
            }
            headers = {"Content-Type": "application/json"}

            try:
                async with session.put(self.url, json=batch_data, headers=headers) as response:
                    if self.is_down:  # Log recovery if previously down
                        self.logger.info("Node recovered successfully")
                    self.is_down = False
                    return await response.text()
            except aiohttp.ClientConnectorError as e:
                self.is_down = True
                self.logger.error(f"Cannot connect to {self.host}:{self.port}: {str(e)}")
                return None  # Return None to indicate failure, continue execution
            except Exception as e:
                self.logger.error(f"Unexpected error: {str(e)}")
                return None

    async def worker(self, semaphore, session):
        """Worker that sends requests while respecting concurrency limits."""
        response = await self.send_batch(session, semaphore)
        if response is not None:  # Only append successful responses
            self.results.append(response)

    async def run(self):
        """Execute the stress test with configured parameters, continue despite failures."""
        semaphore = asyncio.Semaphore(self.concurrent_requests)
        self.results = []
        round_num = 0
        self.start_time = time.time()

        self.logger.info(f"Starting NodeClient for {self.host}:{self.port}")

        async with aiohttp.ClientSession() as session:
            total_requests = 0
            while True:
                round_num += 1
                elapsed_time = time.time() - self.start_time
                expected_requests = int(elapsed_time * self.requests_per_second)
                requests_to_send = min(self.requests_per_second,
                                       self.requests_per_second - (total_requests - expected_requests))

                if requests_to_send > 0:
                    tasks = [self.worker(semaphore, session) for _ in range(requests_to_send)]
                    await asyncio.gather(*tasks)
                    total_requests += requests_to_send  # Count attempts regardless of success

                current_time = time.time()
                successful_requests = len(self.results)  # Only successful requests
                actual_rps = successful_requests / (current_time - self.start_time) if (
                                                                                                   current_time - self.start_time) > 0 else 0

                if int(current_time - self.start_time) > int(elapsed_time):
                    self.logger.info(
                        f"Round: {round_num}, "
                        f"Time: {int(current_time - self.start_time)}s, "
                        f"Total Attempts: {total_requests}, "
                        f"Successful Requests: {successful_requests}, "
                        f"Actual RPS: {actual_rps:.2f}"
                    )

                if actual_rps > self.requests_per_second and not self.is_down:
                    sleep_time = (total_requests / self.requests_per_second) - (current_time - self.start_time)
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.001)  # Small sleep to prevent tight loop


async def main():
    client = NodeClient(
        host='localhost',
        port=6001,
        requests_per_second=10,
        concurrent_requests=2
    )
    try:
        await client.run()
    except KeyboardInterrupt:
        end_time = time.time()
        duration = end_time - client.start_time
        client.logger.info(f"Stopped after {len(client.results)} requests")
        if duration > 0:
            client.logger.info(f"Average RPS: {len(client.results) / duration:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
