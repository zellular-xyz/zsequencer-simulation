import json
import os
import secrets
import shutil
from typing import Any

from eigensdk.crypto.bls import attestation
from pydantic import BaseModel
from web3 import Account

import simulations.utils as simulations_utils
from simulations.config import SimulationConfig


class Keys(BaseModel):
    bls_private_key: str
    bls_key_pair: Any
    ecdsa_private_key: str


APPS = {
    "simple_app": {
        "url": "",
        "public_keys": []
    },
    "orderbook": {
        "url": "",
        "public_keys": []
    },
    "new_app": {
        "url": "",
        "public_keys": []
    },
    "new_app2": {
        "url": "",
        "public_keys": []
    },
    "your-app-name": {
        "url": "",
        "public_keys": []
    },
    "your-app-name2": {
        "url": "",
        "public_keys": []
    },
    "your-me": {
        "url": "",
        "public_keys": []
    },
    "test": {
        "url": "",
        "public_keys": []
    }
}


def generate_keys() -> Keys:
    bls_private_key: str = secrets.token_hex(32)
    bls_key_pair: attestation.KeyPair = attestation.new_key_pair_from_string(bls_private_key)
    ecdsa_private_key: str = secrets.token_hex(32)

    return Keys(bls_private_key=bls_private_key,
                bls_key_pair=bls_key_pair,
                ecdsa_private_key=ecdsa_private_key)


def generate_node_info(node_idx, keys: Keys):
    address = Account().from_key(keys.ecdsa_private_key).address.lower()
    return dict(id=address,
                public_key_g2=keys.bls_key_pair.pub_g2.getStr(10).decode("utf-8"),
                address=address,
                socket=f"http://localhost:{str(6000 + node_idx)}",
                stake=10)


def prepare_simulation_directory(simulation_conf):
    for filename in os.listdir(simulation_conf.DST_DIR):
        file_path = os.path.join(simulation_conf.DST_DIR, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

    with open(os.path.join(simulation_conf.DST_DIR, 'apps.json'), "w") as file:
        json.dump(APPS, file, indent=4)


def main():
    num_nodes = 4
    simulation_conf = SimulationConfig(ZSEQUENCER_NODES_SOURCE="file")

    nodes_key_mapping = {}

    for node_idx in range(num_nodes):
        keys = generate_keys()
        node_address = Account().from_key(keys.ecdsa_private_key).address.lower()
        nodes_key_mapping[node_address] = keys

    sorted_addresses = sorted(list(nodes_key_mapping.keys()))
    sequencer_address = sorted_addresses[0]

    nodes_execution_args = {}
    nodes_info = {}
    for node_idx, node_address in enumerate(sorted_addresses):
        keys = nodes_key_mapping[node_address]
        simulation_conf.prepare_node(node_idx=node_idx, keys=keys)
        node_info = generate_node_info(node_idx, nodes_key_mapping[node_address])
        nodes_info[node_address] = node_info
        nodes_execution_args[node_address] = {
            'node_execution_cmd': simulations_utils.generate_node_execution_command(node_idx),
            'env_variables': simulation_conf.to_dict(node_idx=node_idx,
                                                     sequencer_initial_address=sequencer_address)
        }

    with open(os.path.join(simulation_conf.DST_DIR, 'nodes.json'), "w") as file:
        json.dump(nodes_info, file, indent=4)

    for _, args in nodes_execution_args.items():
        simulations_utils.bootstrap_node(**args)


if __name__ == "__main__":
    main()
