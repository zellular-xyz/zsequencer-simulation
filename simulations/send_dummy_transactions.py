import asyncio

from simulations.concurrent_batch_sender import BatchSender
from simulations.file_logger import FileLogger


def send_batches_process(process_idx):
    file_logger_path = f'/private/tmp/zellular-simulation-logs/simulations_{str(process_idx)}.log'
    node_sockets = ['http://localhost:6001']

    file_logger = FileLogger(file_path=file_logger_path)
    batch_sender = BatchSender(logger=file_logger, app_name="simple_app")

    batch_sender.set_node_sockets(node_sockets=node_sockets)
    asyncio.run(batch_sender.send_batches_concurrently())
