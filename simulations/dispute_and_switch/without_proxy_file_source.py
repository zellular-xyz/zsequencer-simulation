import json
import os
import secrets
import shutil
from typing import Any

from eigensdk.crypto.bls import attestation
from pydantic import BaseModel
from web3 import Account

import simulations.utils as simulations_utils


class Keys(BaseModel):
    bls_private_key: str
    bls_key_pair: Any
    ecdsa_private_key: str


DST_DIR = "/tmp/zellular_dev_net/"
VERSION = "v0.0.14"
BASE_PORT = 6000

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




def generate_envs(node_idx, sequencer_address):
    return {
        "ZSEQUENCER_BLS_KEY_FILE": os.path.join(DST_DIR, f"bls_key_{node_idx}.json"),
        "ZSEQUENCER_BLS_KEY_PASSWORD": f'a{node_idx}',
        "ZSEQUENCER_ECDSA_KEY_FILE": os.path.join(DST_DIR, f"ecdsa_key_{node_idx}.json"),
        "ZSEQUENCER_ECDSA_KEY_PASSWORD": f'b{node_idx}',
        "ZSEQUENCER_NODES_FILE": '/tmp/zellular_dev_net/nodes.json',
        "ZSEQUENCER_APPS_FILE": '/tmp/zellular_dev_net/apps.json',
        "ZSEQUENCER_SNAPSHOT_PATH": os.path.join(DST_DIR, f"db_{node_idx}"),
        "ZSEQUENCER_HISTORICAL_NODES_REGISTRY": "",
        "ZSEQUENCER_PORT": str(BASE_PORT + node_idx),
        "ZSEQUENCER_SNAPSHOT_CHUNK": str(7000),
        "ZSEQUENCER_REMOVE_CHUNK_BORDER": str(3),
        "ZSEQUENCER_THRESHOLD_PERCENT": str(42),
        "ZSEQUENCER_SEND_TXS_INTERVAL": str(0.05),
        "ZSEQUENCER_SYNC_INTERVAL": str(0.05),
        "ZSEQUENCER_FINALIZATION_TIME_BORDER": str(10),
        "ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT": str(5),
        "ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL": str(70),
        "ZSEQUENCER_API_BATCHES_LIMIT": str(5000),
        "ZSEQUENCER_INIT_SEQUENCER_ID": sequencer_address,
        "ZSEQUENCER_NODES_SOURCE": "file",
        "ZSEQUENCER_REGISTER_OPERATOR": "false",
        "ZSEQUENCER_VERSION": VERSION}


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


def prepare_node(node_idx: int, keys: Keys):
    data_dir: str = f"{DST_DIR}/db_{node_idx}"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)

    bls_key_file: str = f"{DST_DIR}/bls_key_{node_idx}.json"
    bls_passwd: str = f'a{node_idx}'
    bls_key_pair: attestation.KeyPair = attestation.new_key_pair_from_string(keys.bls_private_key)
    bls_key_pair.save_to_file(bls_key_file, bls_passwd)

    ecdsa_key_file: str = f"{DST_DIR}/ecdsa_key_{node_idx}.json"
    ecdsa_passwd: str = f'b{node_idx}'
    encrypted_json = Account.encrypt(keys.ecdsa_private_key, ecdsa_passwd)
    with open(ecdsa_key_file, 'w') as f:
        f.write(json.dumps(encrypted_json))


def main():
    num_nodes = 3

    sequencer_address = None
    nodes_info = {}

    for filename in os.listdir(DST_DIR):
        file_path = os.path.join(DST_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Removed {file_path}")
        except Exception as e:
            print(f"Error removing {file_path}: {e}")

    with open(f"{DST_DIR}/apps.json", "w") as file:
        json.dump(APPS, file, indent=4)

    for node_idx in range(num_nodes):
        keys = generate_keys()
        node_info = generate_node_info(node_idx, keys)
        nodes_info[node_info['id']] = node_info
        prepare_node(node_idx, keys)
        if node_idx == 0:
            sequencer_address = node_info['id']

    with open(f"{DST_DIR}/nodes.json", "w") as file:
        json.dump(nodes_info, file, indent=4)

    nodes_execution_args = {}
    for idx in range(num_nodes):
        nodes_execution_args[idx] = {
            'node_execution_cmd': simulations_utils.generate_node_execution_command(idx),
            'env_variables': generate_envs(idx, sequencer_address)
        }

    for _, args in nodes_execution_args.items():
        simulations_utils.bootstrap_node(**args)


if __name__ == "__main__":
    main()
