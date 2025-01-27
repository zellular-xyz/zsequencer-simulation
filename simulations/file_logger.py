import threading
import time
import os
from queue import Queue


def create_file_with_parents(file_path):
    parent_dir = os.path.dirname(file_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    with open(file_path, 'w'):
        pass


class FileLogger:
    def __init__(self, file_path: str, flush_interval: float = 1.0):
        """
        Initializes the FileLogger.

        :param file_path: Path to the file where logs will be written.
        :param flush_interval: Time interval (in seconds) between buffer flushes.
        """
        self.file_path = file_path
        self.flush_interval = flush_interval
        self.buffer = Queue()
        self.shutdown_event = threading.Event()
        self.flush_thread = threading.Thread(target=self._flush_buffer_periodically, daemon=True)
        self.lock = threading.Lock()

        # Ensure the file and its parent directories exist
        create_file_with_parents(self.file_path)

        # Start the flushing thread
        self.flush_thread.start()

    def log(self, message: str):
        """
        Adds a log message to the buffer.

        :param message: The log message to be added.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        formatted_message = f"[{timestamp}] {message}"
        self.buffer.put(formatted_message)

    def _flush_buffer(self):
        """
        Writes all messages from the buffer to the file.
        """
        with self.lock:
            # Retrieve all items from the queue at once
            messages = []
            while not self.buffer.empty():
                messages.append(self.buffer.get())

            # Write all messages to the file
            if messages:
                with open(self.file_path, 'a') as file:
                    file.write('\n'.join(messages) + '\n')

    def _flush_buffer_periodically(self):
        """
        Periodically flushes the buffer to the file.
        """
        while not self.shutdown_event.is_set():
            time.sleep(self.flush_interval)
            self._flush_buffer()

    def shutdown(self):
        """
        Stops the flushing thread and flushes any remaining messages in the buffer to the file.
        """
        self.shutdown_event.set()
        self.flush_thread.join()
        self._flush_buffer()
