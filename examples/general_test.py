"""This script simulates a simple app which uses Zsequencer."""

import argparse
import json
import logging
import threading
import time
import math
import random
import string
from typing import Any, List, Dict

import requests
from requests.exceptions import RequestException

BATCH_SIZE: int = 500
BATCH_NUMBER: int = 200
CHECK_STATE_INTERVAL: float = 0.05
THREAD_NUMBERS_FOR_SENDING_TXS = 50

# Configure logging at the start
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This sends logs to console
    ]
)

zlogger = logging.getLogger(__name__)


def check_state(
        app_name: str, node_url: str, batch_number: int, batch_size: int
) -> None:
    """Continuously check the node state until all the batches are finalized."""
    start_time: float = time.time()
    while True:
        try:
            response: requests.Response = requests.get(
                f"{node_url}/node/{app_name}/batches/finalized/last"
            )
            response.raise_for_status()
            last_finalized_batch: dict[str, Any] = response.json()["data"]
            last_finalized_index: int = last_finalized_batch.get("index", 0)
            zlogger.info(
                f"Last finalized index: {last_finalized_index} -  ({time.time() - start_time} s)"
            )
            if last_finalized_index == batch_number:
                break
        except RequestException as error:
            zlogger.error(f"Error checking state: {error}")
        time.sleep(CHECK_STATE_INTERVAL)


def send_batches(app_name: str, batches: list[dict[str, Any]], node_url: str, thread_index: int) -> None:
    """Send multiple batches of transactions to the node."""
    for i, batch in enumerate(batches):
        zlogger.info(f'Thread {thread_index}: sending batch {i + 1} with {len(batch)} transactions')
        try:
            string_data: str = json.dumps(batch)
            response: requests.Response = requests.put(
                url=f"{node_url}/node/{app_name}/batches",
                data=string_data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except RequestException as error:
            zlogger.error(f"Thread {thread_index}: Error sending batch of transactions: {error}")


def send_batches_with_threads(
        app_name: str, batches: list[dict[str, Any]], node_url: str, num_threads: int = 100
) -> None:
    """Send batches of transactions to the node using multiple threads."""
    num_batches = len(batches)
    # Adjust number of threads if there are fewer batches than threads
    if num_batches < num_threads:
        num_threads = num_batches

    threads = []
    batches_per_thread = math.ceil(num_batches / num_threads)

    for i in range(num_threads):
        start_index = i * batches_per_thread
        end_index = min(start_index + batches_per_thread, num_batches)
        batch_subset = batches[start_index:end_index]

        if not batch_subset:
            break

        thread = threading.Thread(target=send_batches, args=(app_name, batch_subset, node_url, i))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for t in threads:
        t.join()

    zlogger.info("All batches have been sent.")


def send_batches_in_bulk_mode(node_url: str, app_name: str, batches_count: int, bulk_count: int):
    iteration_batches_count = batches_count // bulk_count
    for iteration in range(bulk_count):
        zlogger.info(f'Sending {iteration_batches_count} batches in iteration {iteration}')

        try:
            response: requests.Response = requests.put(
                url=f"{node_url}/node/batches",
                data=json.dumps({app_name: generate_dummy_batches(batch_size=10, batches_count=batches_count)}),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except RequestException:
            zlogger.error(f"Error occurred while sending batches in iteration {iteration}")


def generate_random_string(length=15):
    characters = string.ascii_letters + string.digits  # a-zA-Z0-9
    return ''.join(random.choice(characters) for _ in range(length))


def generate_dummy_batches(
        batch_size: int, batches_count: int
) -> List[List[Dict]]:
    """Create batches of transactions."""
    return [
        [{
            "operation": "foo",
            "serial": generate_random_string(),
            "version": 6,
        } for _ in range(batch_size)]
        for _ in range(batches_count)]


TOTAL_BATCHES_COUNT = 10_000
BULK_COUNT = 10


def main() -> None:
    """Run the simple app."""
    app_name = 'simple_app'
    node_url = 'http://localhost:6002'

    sender_thread: threading.Thread = threading.Thread(
        target=send_batches_in_bulk_mode, args=[node_url, app_name, TOTAL_BATCHES_COUNT, BULK_COUNT]
    )

    sync_thread: threading.Thread = threading.Thread(
        target=check_state,
        args=[app_name, node_url, BATCH_NUMBER, BATCH_SIZE],
    )

    sender_thread.start()
    sync_thread.start()

    sender_thread.join()
    sync_thread.join()


if __name__ == "__main__":
    main()
