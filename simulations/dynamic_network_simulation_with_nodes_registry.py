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

    def generate_node_info(self, node_idx: int, keys: simulations_utils.Keys) -> NodeInfo:
        address = Account().from_key(keys.ecdsa_private_key).address.lower()
        return NodeInfo(id=address,
                        public_key_g2=keys.bls_key_pair.pub_g2.getStr(10).decode("utf-8"),
                        address=address,
                        socket=f"{self.simulation_config.HOST}:{str(self.simulation_config.BASE_PORT + node_idx)}",
                        stake=10)

    def prepare_node(self,
                     node_idx: int,
                     keys: simulations_utils.Keys,
                     sequencer_initial_address: str) -> Tuple[str, Dict]:

        DST_DIR = self.simulation_config.DST_DIR
        data_dir: str = f"{DST_DIR}/db_{node_idx}"
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)

        bls_key_file: str = f"{DST_DIR}/bls_key{node_idx}.json"
        bls_passwd: str = f'a{node_idx}'
        bls_key_pair: attestation.KeyPair = attestation.new_key_pair_from_string(keys.bls_private_key)
        bls_key_pair.save_to_file(bls_key_file, bls_passwd)

        ecdsa_key_file: str = f"{DST_DIR}/ecdsa_key{node_idx}.json"
        ecdsa_passwd: str = f'b{node_idx}'
        encrypted_json = Account.encrypt(keys.ecdsa_private_key, ecdsa_passwd)
        with open(ecdsa_key_file, 'w') as f:
            f.write(json.dumps(encrypted_json))

        env_variables = {
            "ZSEQUENCER_BLS_KEY_FILE": bls_key_file,
            "ZSEQUENCER_BLS_KEY_PASSWORD": bls_passwd,
            "ZSEQUENCER_ECDSA_KEY_FILE": ecdsa_key_file,
            "ZSEQUENCER_ECDSA_KEY_PASSWORD": ecdsa_passwd,
            "ZSEQUENCER_SNAPSHOT_PATH": data_dir,
            "ZSEQUENCER_REGISTER_OPERATOR": "false",
            "ZSEQUENCER_VERSION": "v0.0.13",
            "ZSEQUENCER_NODES_FILE": "",
            **self.simulation_config.to_dict(node_idx=node_idx,
                                             sequencer_initial_address=sequencer_initial_address)
        }

        return simulations_utils.generate_node_execution_command(node_idx), env_variables

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
        sequencer_address = None
        initialized_network_snapshot: SnapShotType = {}
        execution_cmds = {}
        for node_idx in range(nodes_number):
            keys = simulations_utils.generate_keys()
            node_info = self.generate_node_info(node_idx=node_idx, keys=keys)
            if node_idx == 0:
                sequencer_address = node_info.id

            initialized_network_snapshot[node_info.id] = node_info
            execution_cmds[node_info.id] = self.prepare_node(node_idx=node_idx,
                                                             keys=keys,
                                                             sequencer_initial_address=sequencer_address)

        self.nodes_registry_client.add_snapshot(initialized_network_snapshot)

        for node_address, (cmd, env_variables) in execution_cmds.items():
            simulations_utils.launch_node(cmd, env_variables)

        self.sequencer_address, self.network_nodes_state = sequencer_address, initialized_network_snapshot

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
            for node_address, (cmd, env_variables) in new_nodes_cmds.items():
                simulations_utils.launch_node(cmd, env_variables)

        self.network_nodes_state = next_network_state
        self.nodes_registry_client.add_snapshot(self.network_nodes_state)

    def simulate_network_nodes_transition(self):
        simulations_utils.delete_directory_contents(self.simulation_config.DST_DIR)

        if not os.path.exists(self.simulation_config.DST_DIR):
            os.makedirs(self.simulation_config.DST_DIR)

        script_dir: str = os.path.dirname(os.path.abspath(__file__))
        parent_dir: str = os.path.dirname(script_dir)
        os.chdir(parent_dir)

        with open(file=self.simulation_config.APPS_FILE, mode="w", encoding="utf-8") as file:
            file.write(json.dumps({f"{self.simulation_config.APP_NAME}": {"url": "", "public_keys": []}}))

        self.initialize_network(self.simulation_config.TIMESERIES_NODES_COUNT[0])

        timeseries_nodes_last_idx = self.get_timeseries_last_node_idx()
        for next_network_state_idx in range(1, len(self.simulation_config.TIMESERIES_NODES_COUNT) - 1):
            time.sleep(15)
            self.transfer_state(
                next_network_nodes_number=self.simulation_config.TIMESERIES_NODES_COUNT[next_network_state_idx],
                nodes_last_index=timeseries_nodes_last_idx[next_network_state_idx - 1])

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
    DynamicNetworkSimulation(simulation_config=SimulationConfig()).run()


if __name__ == "__main__":
    simulate_dynamic_network()
