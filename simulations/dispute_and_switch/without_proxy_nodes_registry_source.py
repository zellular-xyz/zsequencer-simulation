import logging
import socket
import threading
import time

import simulations.utils as simulations_utils
from historical_nodes_registry import (NodesRegistryClient,
                                       SnapShotType,
                                       run_registry_server)
from simulations.config import SimulationConfig
from simulations.schema import ExecutionData


class DisputeAndSwitchSimulation:

    def __init__(self, simulation_config: SimulationConfig, logger):
        self.simulation_config = simulation_config
        self.nodes_registry_thread = None
        self.network_state_handler_thread = None
        self.send_transactions_thread = None
        self.sequencer_address = None
        self.network_nodes_state = None
        self.shutdown_event = threading.Event()
        self.nodes_registry_client = NodesRegistryClient(socket=self.simulation_config.HISTORICAL_NODES_REGISTRY_SOCKET)
        self.logger = logger

    def wait_nodes_registry_server(self, timeout: float = 20.0, interval: float = 0.5):
        start_time = time.time()
        host, port = self.simulation_config.HISTORICAL_NODES_REGISTRY_HOST, self.simulation_config.HISTORICAL_NODES_REGISTRY_PORT

        while time.time() - start_time < timeout:
            try:
                with socket.create_connection((host, port), timeout=interval):
                    self.logger.info(f"Server is up and running on {host}:{port}")
                    return
            except (socket.timeout, ConnectionRefusedError):
                self.logger.info(f"Waiting for server at {host}:{port}...")
                time.sleep(interval)
        raise TimeoutError(f"Server did not start within {timeout} seconds.")

    def initialize_network(self, nodes_number: int):
        sequencer_address, network_keys = simulations_utils.generate_network_keys(network_nodes_num=nodes_number)
        initialized_network_snapshot: SnapShotType = {}
        execution_cmds = {}

        for node_idx, key_data in enumerate(network_keys):
            initialized_network_snapshot[key_data.address] = simulations_utils.generate_node_info(node_idx=node_idx,
                                                                                                  key_data=key_data)
            self.simulation_config.prepare_node(node_idx=node_idx, keys=key_data.keys)
            execution_cmds[key_data.address] = ExecutionData(
                execution_cmd=simulations_utils.generate_node_execution_command(node_idx),
                env_variables=self.simulation_config.to_dict(node_idx=node_idx,
                                                             sequencer_initial_address=sequencer_address))

        self.nodes_registry_client.add_snapshot(initialized_network_snapshot)

        for _, execution_data in execution_cmds.items():
            simulations_utils.bootstrap_node(env_variables=execution_data.env_variables,
                                             node_execution_cmd=execution_data.execution_cmd)

    def run(self):
        simulations_utils.remove_directory(self.simulation_config.DST_DIR)
        self.nodes_registry_thread = threading.Thread(
            target=run_registry_server,
            args=(self.simulation_config.HISTORICAL_NODES_REGISTRY_HOST,
                  self.simulation_config.HISTORICAL_NODES_REGISTRY_PORT),
            daemon=True)
        self.nodes_registry_thread.start()

        try:
            self.wait_nodes_registry_server()
        except TimeoutError as e:
            self.logger.error(f"Error: {e}")
            return

        self.logger.info("Historical Nodes Registry server is running. Press Ctrl+C to stop.")

        self.initialize_network(nodes_number=4)
        self.shutdown_event.wait()


def simulate_dispute_and_switch_without_proxy():
    DisputeAndSwitchSimulation(simulation_config=SimulationConfig(
        ZSEQUENCER_NODES_SOURCE="historical_nodes_registry",
        TIMESERIES_NODES_COUNT=[4]),
        logger=logging.getLogger(__name__)).run()


if __name__ == "__main__":
    simulate_dispute_and_switch_without_proxy()
