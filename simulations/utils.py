"""This script sets up and runs a simple app network for testing."""
import os
import random
import secrets
import shutil
import json
import string
from uuid import uuid4
from typing import Dict, List, Any, Tuple
from simulations.schema import Keys, KeyData
from eigensdk.crypto.bls import attestation
from historical_nodes_registry import NodeInfo
from pydantic import BaseModel
from web3 import Account
import config
from terminal_exeuction import run_command_on_terminal


def generate_keys() -> Keys:
    bls_private_key: str = secrets.token_hex(32)
    bls_key_pair: attestation.KeyPair = attestation.new_key_pair_from_string(bls_private_key)
    ecdsa_private_key: str = secrets.token_hex(32)

    return Keys(bls_private_key=bls_private_key,
                bls_key_pair=bls_key_pair,
                ecdsa_private_key=ecdsa_private_key)


def generate_network_keys(network_nodes_num: int) -> Tuple[str, List[KeyData]]:
    network_keys = []

    for _ in range(network_nodes_num):
        keys = generate_keys()
        address = Account().from_key(keys.ecdsa_private_key).address.lower()
        network_keys.append(KeyData(keys=keys, address=address))

    network_keys = sorted(network_keys, key=lambda network_key: network_key.address)
    sequencer_address = network_keys[0].address

    return sequencer_address, network_keys


BASE_NODE_PORT = 6001
BASE_PROXY_PORT = 7001


def generate_node_info(node_idx: int, key_data: KeyData, stake: int = 10):
    return NodeInfo(id=key_data.address,
                    public_key_g2=key_data.keys.bls_key_pair.pub_g2.getStr(10).decode("utf-8"),
                    address=key_data.address,
                    socket=f"http://localhost:{str(BASE_NODE_PORT + node_idx)}",
                    stake=stake)


def prepare_simulation_directory(simulation_conf):
    for filename in os.listdir(simulation_conf.DST_DIR):
        file_path = os.path.join(simulation_conf.DST_DIR, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

    with open(os.path.join(simulation_conf.DST_DIR, 'apps.json'), "w") as file:
        json.dump(simulation_conf.APPS, file, indent=4)


def generate_node_execution_command(node_idx: int) -> str:
    """Run a command in a new terminal tab."""
    script_dir: str = os.path.dirname(os.path.abspath(__file__))
    parent_dir: str = os.path.dirname(script_dir)
    os.chdir(parent_dir)

    virtual_env_path = os.path.join(config.ZSEQUENCER_PROJECT_ROOT, config.ZSEQUENCER_PROJECT_VIRTUAL_ENV)
    node_runner_path = os.path.join(config.ZSEQUENCER_PROJECT_ROOT, 'run.py')

    return f"source {virtual_env_path}; python -u {node_runner_path} {str(node_idx)}; echo; read -p 'Press enter to exit...'"


def generate_node_proxy_execution_command(port, workers) -> str:
    """Run a command in a new terminal tab."""
    script_dir: str = os.path.dirname(os.path.abspath(__file__))
    parent_dir: str = os.path.dirname(script_dir)
    os.chdir(parent_dir)

    proxy_runner_path = 'proxy_server'
    server_app = 'app'

    return f"cd {config.ZSEQUENCER_PROJECT_ROOT} && source {config.ZSEQUENCER_PROJECT_VIRTUAL_ENV} && uvicorn --app-dir proxy {proxy_runner_path}:{server_app} --host 0.0.0.0 --port {port} --workers {workers}"


def remove_directory(path: str) -> None:
    """
    Remove a directory and its contents using shutil.

    Args:
        path: Path to the directory to remove.
    """
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            print(f"Removed {path} and its contents")
        except OSError as e:
            print(f"Error: {e}")
    else:
        print(f"Directory {path} does not exist")


def launch_node(cmd, env_variables):
    run_command_on_terminal(cmd, env_variables)


def bootstrap_node(env_variables, node_execution_cmd, proxy_execution_cmd=None):
    run_command_on_terminal(node_execution_cmd, env_variables)
    if proxy_execution_cmd is not None:
        run_command_on_terminal(proxy_execution_cmd, env_variables)


def generate_transactions(batch_size: int) -> List[Dict]:
    return [
        {
            "operation": "foo",
            "serial": str(uuid4()),
            "version": 6,
        } for _ in range(batch_size)
    ]


APPS = {
    "simple_app": {
        "url": "",
        "public_keys": []
    }
}
