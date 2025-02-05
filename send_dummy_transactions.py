import asyncio
import multiprocessing
from multiprocessing import Process

from simulations.concurrent_batch_sender import BatchSender
from simulations.file_logger import FileLogger


def send_batches_process(process_idx):
    file_logger_path = f'/private/tmp/zellular-simulation-logs/simulations_{str(process_idx)}.log'
    node_sockets = ['http://localhost:6001']

    file_logger = FileLogger(file_path=file_logger_path)
    batch_sender = BatchSender(logger=file_logger, app_name="simple_app")

    batch_sender.set_node_sockets(node_sockets=node_sockets)
    asyncio.run(batch_sender.send_batches_concurrently())


def main(max_workers=None):
    if max_workers is None:
        max_workers = multiprocessing.cpu_count()  # Set to the number of available CPU cores

    processes = [
        Process(target=send_batches_process, args=(process_idx,))
        for process_idx in range(max_workers)
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join()


if __name__ == '__main__':
    main()  # Uses all available CPUs by default
