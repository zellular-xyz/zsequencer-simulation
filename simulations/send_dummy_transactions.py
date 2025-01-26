import asyncio
import json
import time
from uuid import uuid4

import aiohttp
from aiohttp import ClientSession

base_url = 'http://localhost:6001'
app_name = 'simple_app'


async def send_batch(session: ClientSession):
    """
    Sends a single batch of transactions using aiohttp.
    """
    try:
        t = int(time.time())
        batch = [{"tx_id": str(uuid4()), "operation": "foo", "t": t} for _ in range(20)]
        string_data = json.dumps(batch)

        async with session.put(
                url=f"{base_url}/node/{app_name}/batches",
                data=string_data,
                headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                print(f"Batch sent successfully at {time.ctime()}")
            else:
                print(f"Failed with status code {response.status}")
    except Exception as error:
        print(f"Error sending batch of transactions: {error}")


async def send_batches_concurrently():
    requests_per_second = 100

    async with aiohttp.ClientSession() as session:
        while True:
            tasks = [
                send_batch(session)
                for _ in range(requests_per_second)
            ]
            await asyncio.gather(*tasks)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(send_batches_concurrently())
