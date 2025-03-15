from clients.node_client import NodeClient
import asyncio
import time


async def main():
    client = NodeClient(
        host='localhost',
        port=6002,
        requests_per_second=1000,
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
