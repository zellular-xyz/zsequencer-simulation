import asyncio

from simulations.send_dummy_transactions import send_batches_concurrently


def main():
    asyncio.run(send_batches_concurrently())


if __name__ == "__main__":
    main()
