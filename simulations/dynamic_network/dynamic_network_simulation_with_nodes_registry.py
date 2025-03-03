"""This script sets up and runs a simple app network for testing."""
import copy
import json
import os
import random
import shutil
import socket
import threading
import time
from functools import reduce
from typing import Dict, Tuple

import requests
from eigensdk.crypto.bls import attestation
from requests.exceptions import RequestException
from web3 import Account

import simulations.utils as simulations_utils
from historical_nodes_registry import (NodesRegistryClient,
                                       NodeInfo,
                                       SnapShotType,
                                       run_registry_server)
from simulations.config import SimulationConfig
from simulations.schema import ExecutionData


class DynamicNetworkSimulation:

    def __init__(self, simulation_config: SimulationConfig):
        self.simulation_config = simulation_config
        self.nodes_registry_thread = None
        self.network_transition_thread = None
        self.send_batches_thread = None
        self.sequencer_address = None
        self.network_nodes_state = None
        self.shutdown_event = threading.Event()
        self.nodes_registry_client = NodesRegistryClient(socket=self.simulation_config.HISTORICAL_NODES_REGISTRY_SOCKET)

    def get_timeseries_last_node_idx(self):
        timeseries_nodes_count = self.simulation_config.TIMESERIES_NODES_COUNT

        return reduce(lambda acc,
                             i: acc + [acc[-1] + (timeseries_nodes_count[i] - timeseries_nodes_count[i - 1])
                                       if timeseries_nodes_count[i - 1] < timeseries_nodes_count[i]
                                       else acc[-1]], range(1, len(timeseries_nodes_count)),
                      [timeseries_nodes_count[0] - 1])

    def wait_nodes_registry_server(self, timeout: float = 20.0, interval: float = 0.5):
        start_time = time.time()
        host, port = self.simulation_config.HISTORICAL_NODES_REGISTRY_HOST, self.simulation_config.HISTORICAL_NODES_REGISTRY_PORT

        while time.time() - start_time < timeout:
            try:
                with socket.create_connection((host, port), timeout=interval):
                    print(f"Server is up and running on {host}:{port}")
                    return
            except (socket.timeout, ConnectionRefusedError):
                print(f"Waiting for server at {host}:{port}...")
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

    def transfer_state(self, next_network_nodes_number: int, nodes_last_index: int):
        current_network_nodes_number = len(self.network_nodes_state)
        next_network_state = copy.deepcopy(self.network_nodes_state)

        if current_network_nodes_number < next_network_nodes_number:
            first_new_node_idx = nodes_last_index + 1
            new_nodes_number = next_network_nodes_number - current_network_nodes_number
            new_nodes_cmds = {}
            for node_idx in range(first_new_node_idx, first_new_node_idx + new_nodes_number):
                keys = simulations_utils.generate_keys()
                node_info = self.generate_node_info(node_idx=node_idx, keys=keys)
                next_network_state[node_info.id] = node_info

                new_nodes_cmds[node_info.id] = self.prepare_node(node_idx=node_idx,
                                                                 keys=keys,
                                                                 sequencer_initial_address=self.sequencer_address)

            self.nodes_registry_client.add_snapshot(next_network_state)
            for node_address, execution_dict in new_nodes_cmds.items():
                node_execution_cmd, proxy_execution_cmd, env_variables = (execution_dict['node_execution_cmd'],
                                                                          execution_dict['proxy_execution_cmd'],
                                                                          execution_dict['env_variables'])

                simulations_utils.launch_node(node_execution_cmd, env_variables)
                simulations_utils.launch_node(proxy_execution_cmd, env_variables)

        self.network_nodes_state = next_network_state
        self.nodes_registry_client.add_snapshot(self.network_nodes_state)

    def simulate_network_nodes_transition(self):
        # simulations_utils.delete_directory_contents(self.simulation_config.DST_DIR)
        #
        # if not os.path.exists(self.simulation_config.DST_DIR):
        #     os.makedirs(self.simulation_config.DST_DIR)
        #
        # script_dir: str = os.path.dirname(os.path.abspath(__file__))
        # parent_dir: str = os.path.dirname(script_dir)
        # os.chdir(parent_dir)
        #
        # with open(file=self.simulation_config.apps_file, mode="w", encoding="utf-8") as file:
        #     file.write(json.dumps({f"{self.simulation_config.APP_NAME}": {"url": "", "public_keys": []}}))

        self.initialize_network(self.simulation_config.TIMESERIES_NODES_COUNT[0])

        # timeseries_nodes_last_idx = self.get_timeseries_last_node_idx()
        # for next_network_state_idx in range(1, len(self.simulation_config.TIMESERIES_NODES_COUNT) - 1):
        #     time.sleep(15)
        #     self.transfer_state(
        #         next_network_nodes_number=self.simulation_config.TIMESERIES_NODES_COUNT[next_network_state_idx],
        #         nodes_last_index=timeseries_nodes_last_idx[next_network_state_idx - 1])

    def simulate_send_batches(self):
        sending_batches_count = 0
        while sending_batches_count < 10:
            if self.network_nodes_state and self.sequencer_address:
                random_node_address = random.choice(
                    list(set(list(self.network_nodes_state.keys())) - {self.sequencer_address}))
                node_socket = self.network_nodes_state[random_node_address].socket

                try:
                    string_data = json.dumps(simulations_utils.generate_transactions(random.randint(200, 600)))
                    response: requests.Response = requests.put(
                        url=f"{node_socket}/node/{self.simulation_config.APP_NAME}/batches",
                        data=string_data,
                        headers={"Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    sending_batches_count += 1
                except RequestException as error:
                    print(f"Error sending batch of transactions: {error}")

            time.sleep(0.1)

        print('sending batches completed!')

    def run(self):
        self.nodes_registry_thread = threading.Thread(
            target=run_registry_server,
            args=(self.simulation_config.HISTORICAL_NODES_REGISTRY_HOST,
                  self.simulation_config.HISTORICAL_NODES_REGISTRY_PORT),
            daemon=True)
        self.nodes_registry_thread.start()

        try:
            self.wait_nodes_registry_server()
        except TimeoutError as e:
            print(f"Error: {e}")
            return
        print("Historical Nodes Registry server is running. Press Ctrl+C to stop.")

        self.network_transition_thread = threading.Thread(target=self.simulate_network_nodes_transition)
        self.send_batches_thread = threading.Thread(target=self.simulate_send_batches)

        self.network_transition_thread.start()
        self.send_batches_thread.start()

        self.network_transition_thread.join()
        self.send_batches_thread.join()

        self.shutdown_event.wait()


def simulate_dynamic_network():
    DynamicNetworkSimulation(
        simulation_config=SimulationConfig(ZSEQUENCER_NODES_SOURCE="historical_nodes_registry")).run()


if __name__ == "__main__":
    simulate_dynamic_network()
