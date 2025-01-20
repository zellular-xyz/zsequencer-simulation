import json
import os
import shutil
import time
import socket
from typing import Dict, Tuple

from eigensdk.crypto.bls import attestation
from web3 import Account

import simulations.utils as simulations_utils
from historical_nodes_registry import (NodeInfo)
from simulations.config import SimulationConfig


class DisputeAndSwitchSimulation:

    def __init__(self, simulation_config: SimulationConfig):
        self.simulation_config = simulation_config
        self.nodes_registry_thread = None

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
