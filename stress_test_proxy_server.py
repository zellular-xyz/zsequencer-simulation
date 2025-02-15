import asyncio
import random
import string
import time
import aiohttp

# Number of requests and concurrency level
TOTAL_REQUESTS = 10_000
CONCURRENT_REQUESTS = 100

# Target URL with dynamic app_name
URL = f"http://0.0.0.0:7001/node/simple_app/batches"


def generate_random_string(length=10):
    """Generate a random alphanumeric string of given length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


async def send_batch(session, semaphore):
    """Send a batch (POST request) to the server with form data."""
    async with semaphore:
        batch_data = {"batch": generate_random_string(10)}  # Random 10-char string
        headers = {"Content-Type": "application/json"}

        async with session.put(URL, json=batch_data, headers=headers) as response:
            return await response.text()


async def worker(semaphore, session, results):
    """Worker that sends requests while respecting concurrency limits."""
    response = await send_batch(session, semaphore)
    results.append(response)


async def stress_test():
    """Main function to send requests concurrently."""
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)  # Limit concurrency
    results = []

    async with aiohttp.ClientSession() as session:
        tasks = [worker(semaphore, session, results) for _ in range(TOTAL_REQUESTS)]

        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()

    print(f"Completed {len(results)} requests in {end_time - start_time:.2f} seconds")
    print(f"Requests per second: {len(results) / (end_time - start_time):.2f}")


# Run the stress test
if __name__ == "__main__":
    asyncio.run(stress_test())
