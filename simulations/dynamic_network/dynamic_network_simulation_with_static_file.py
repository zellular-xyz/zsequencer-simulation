"""This script sets up and runs a simple app network for testing."""

import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import requests
from requests.exceptions import RequestException
from web3 import Account

import simulations.utils as simulations_utils
from historical_nodes_registry import SnapShotType
from simulations.config import SimulationConfig
from simulations.schema import ExecutionData, KeyData


class DynamicNetworkSimulation:

    def __init__(self, simulation_config: SimulationConfig):
        self._simulation_config = simulation_config
        self._network_transition_thread = None
        self._send_batches_thread = None
        self._sequencer_address = None
        self._network_nodes_state = None

    def update_nodes_file(self, sequencer_address: str, nodes_snapshot: SnapShotType):
        snapshot_dict = {node_address: node_info.dict()
                         for node_address, node_info in nodes_snapshot.items()}

        with open(self._simulation_config.ZSEQUENCER_NODES_FILE, "w") as json_file:
            json.dump(snapshot_dict, json_file, indent=4)
        self._sequencer_address, self._network_nodes_state = sequencer_address, nodes_snapshot

    def initialize_network(self, initial_network_nodes_number: int):
        simulations_utils.remove_directory(self._simulation_config.DST_DIR)
        sequencer_address, network_keys = simulations_utils.generate_network_keys(initial_network_nodes_number)

        nodes_execution_args = {}
        nodes_info = {}

        for idx, key_data in enumerate(network_keys):
            self._simulation_config.prepare_node(node_idx=idx, keys=key_data.keys)
            nodes_info[key_data.address] = simulations_utils.generate_node_info(node_idx=idx, key_data=key_data).dict()
            nodes_execution_args[key_data.address] = ExecutionData(
                execution_cmd=simulations_utils.generate_node_execution_command(idx),
                env_variables=self._simulation_config.to_dict(node_idx=idx,
                                                              sequencer_initial_address=sequencer_address))

        self._sequencer_address, self._network_nodes_state = sequencer_address, nodes_info

        with open(self._simulation_config.nodes_file, "w") as file:
            json.dump(nodes_info, file, indent=4)

        with open(self._simulation_config.apps_file, "w") as file:
            json.dump(simulations_utils.APPS, file, indent=4)

        for _, execution_data in nodes_execution_args.items():
            simulations_utils.bootstrap_node(env_variables=execution_data.env_variables,
                                             node_execution_cmd=execution_data.execution_cmd)
            time.sleep(1)

    def transfer_state(self, iteration_idx: int):
        previous_iteration_idx = iteration_idx - 1
        next_network_nodes_number_edition = (self._simulation_config.TIMESERIES_NODES_COUNT[iteration_idx] -
                                             self._simulation_config.TIMESERIES_NODES_COUNT[previous_iteration_idx])
        # Todo: should implement the case of in which nodes are decreasing
        if next_network_nodes_number_edition <= 0:
            return

        new_nodes_keys = []
        for _ in range(next_network_nodes_number_edition):
            keys = simulations_utils.generate_keys()
            address = Account().from_key(keys.ecdsa_private_key).address.lower()
            new_nodes_keys.append(KeyData(keys=keys, address=address))

        nodes_execution_args = {}
        new_nodes_info = {}
        network_nodes_count = len(self._network_nodes_state)

        for idx, key_data in enumerate(new_nodes_keys):
            node_idx = network_nodes_count + idx
            self._simulation_config.prepare_node(node_idx=node_idx, keys=key_data.keys)
            new_nodes_info[key_data.address] = simulations_utils.generate_node_info(node_idx=node_idx,
                                                                                    key_data=key_data).dict()
            nodes_execution_args[key_data.address] = ExecutionData(
                execution_cmd=simulations_utils.generate_node_execution_command(idx),
                env_variables=self._simulation_config.to_dict(node_idx=node_idx,
                                                              sequencer_initial_address=self._sequencer_address))

        self._network_nodes_state = {**self._network_nodes_state, **new_nodes_info}

        with open(self._simulation_config.nodes_file, "w") as file:
            json.dump(self._network_nodes_state, file, indent=4)

        for _, execution_data in nodes_execution_args.items():
            simulations_utils.bootstrap_node(env_variables=execution_data.env_variables,
                                             node_execution_cmd=execution_data.execution_cmd)

    def simulate_network_nodes_transition(self):
        for iteration_idx in range(len(self._simulation_config.TIMESERIES_NODES_COUNT)):
            if iteration_idx == 0:
                initial_network_nodes_count = self._simulation_config.TIMESERIES_NODES_COUNT[0]
                self.initialize_network(initial_network_nodes_count)
                continue

            self.transfer_state(iteration_idx)
            time.sleep(3)

    @staticmethod
    def generate_transactions(batch_size: int) -> List[Dict]:
        return [
            {
                "operation": "foo",
                "serial": tx_num,
                "version": 6,
            } for tx_num in range(batch_size)
        ]

    @staticmethod
    def send_transactions_to_socket(socket, app_name, transactions):
        try:
            string_data = json.dumps(transactions)
            response = requests.put(
                url=f"{socket}/node/{app_name}/batches",
                data=string_data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return True
        except RequestException as error:
            print(f"Error sending batch of transactions to {socket}: {error}")
            return False

    def get_nodes_addresses(self):
        return list(set(list(self._network_nodes_state.keys())) - {self._sequencer_address})

    def simulate_send_batches(self):
        sending_batches_count = 0
        while sending_batches_count < 10:
            if self._network_nodes_state and self._sequencer_address:
                nodes = self.get_nodes_addresses()
                if len(nodes) == 0:
                    continue
                sockets = [self._network_nodes_state[address]['socket'] for address in nodes]

                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        executor.submit(self.send_transactions_to_socket,
                                        socket,
                                        self._simulation_config.APP_NAME,
                                        self.generate_transactions(random.randint(5, 10))): socket
                        for socket in sockets
                    }

                    results = [future.result() for future in as_completed(futures)]

                    # Increment the count if all futures are successful
                    if all(results):
                        sending_batches_count += 1

            time.sleep(10)

        print('sending batches completed!')

    def run(self):
        self._network_transition_thread = threading.Thread(target=self.simulate_network_nodes_transition)
        self._send_batches_thread = threading.Thread(target=self.simulate_send_batches)

        self._network_transition_thread.start()
        self._send_batches_thread.start()

        self._network_transition_thread.join()
        self._send_batches_thread.join()


def main():
    DynamicNetworkSimulation(simulation_config=SimulationConfig()).run()


if __name__ == "__main__":
    main()
