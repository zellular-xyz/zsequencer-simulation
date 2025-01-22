import json
import os
import random
import shutil
import socket
import threading
import time
import logging
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


class DisputeAndSwitchSimulation:

    def __init__(self, simulation_config: SimulationConfig,
                 logger):
        self.simulation_config = simulation_config
        self.nodes_registry_thread = None
        self.send_batches_thread = None
        self.network_state_handler_thread = None
        self.sequencer_address = None
        self.network_nodes_state = None
        self.shutdown_event = threading.Event()
        self.nodes_registry_client = NodesRegistryClient(socket=self.simulation_config.HISTORICAL_NODES_REGISTRY_SOCKET)
        self.logger = logger

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
                    self.logger.info(f"Server is up and running on {host}:{port}")
                    return
            except (socket.timeout, ConnectionRefusedError):
                self.logger.info(f"Waiting for server at {host}:{port}...")
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

        node_ids = list(set(initialized_network_snapshot.keys()) - {sequencer_address})
        late_node_id, rest_node_ids = node_ids[0], node_ids[1:]

        first_stage_nodes = [*rest_node_ids, sequencer_address]
        print('late_node_id', late_node_id, 'first_stage_nodes', first_stage_nodes)

        for node_id in first_stage_nodes:
            (cmd, env_variables) = execution_cmds[node_id]
            simulations_utils.launch_node(cmd, env_variables)

        first_stage_network_state = {node_id: initialized_network_snapshot[node_id]
                                     for node_id in first_stage_nodes}
        self.sequencer_address, self.network_nodes_state = sequencer_address, first_stage_network_state

        time.sleep(600)

        (cmd, env_variables) = execution_cmds[late_node_id]
        simulations_utils.launch_node(cmd, env_variables)
        self.network_nodes_state = initialized_network_snapshot

    def init(self):
        simulations_utils.delete_directory_contents(self.simulation_config.DST_DIR)

        if not os.path.exists(self.simulation_config.DST_DIR):
            os.makedirs(self.simulation_config.DST_DIR)

        script_dir: str = os.path.dirname(os.path.abspath(__file__))
        parent_dir: str = os.path.dirname(script_dir)
        os.chdir(parent_dir)

        with open(file=self.simulation_config.APPS_FILE, mode="w", encoding="utf-8") as file:
            file.write(json.dumps({f"{self.simulation_config.APP_NAME}": {"url": "", "public_keys": []}}))

        self.initialize_network(3)

    def simulate_send_batches(self):
        time.sleep(15)

        sending_batches_count = 0
        while sending_batches_count < 100000:
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
                    self.logger.error(f"Error sending batch of transactions: {error}")

            time.sleep(0.01)

        self.logger.info('sending batches completed!')

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
            self.logger.error(f"Error: {e}")
            return
        self.logger.info("Historical Nodes Registry server is running. Press Ctrl+C to stop.")

        self.network_state_handler_thread = threading.Thread(target=self.init)
        self.send_batches_thread = threading.Thread(target=self.simulate_send_batches)

        self.send_batches_thread.start()
        self.network_state_handler_thread.start()

        self.send_batches_thread.join()
        self.network_state_handler_thread.join()

        self.shutdown_event.wait()


def simulate_dispute_and_switch():
    DisputeAndSwitchSimulation(simulation_config=SimulationConfig(),
                               logger=logging.getLogger(__name__)).run()
