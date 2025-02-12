"""This script sets up and runs a simple app network for testing."""
import os
import random
import secrets
import shutil
import string
from uuid import uuid4
from typing import Dict, List, Any

from eigensdk.crypto.bls import attestation
from pydantic import BaseModel

import config
from terminal_exeuction import run_command_on_terminal


class Keys(BaseModel):
    bls_private_key: str
    bls_key_pair: Any
    ecdsa_private_key: str


def generate_keys() -> Keys:
    bls_private_key: str = secrets.token_hex(32)
    bls_key_pair: attestation.KeyPair = attestation.new_key_pair_from_string(bls_private_key)
    ecdsa_private_key: str = secrets.token_hex(32)

    return Keys(bls_private_key=bls_private_key,
                bls_key_pair=bls_key_pair,
                ecdsa_private_key=ecdsa_private_key)


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

    proxy_runner_path = 'proxy.proxy_server'
    server_app = 'app'

    return f"cd {config.ZSEQUENCER_PROJECT_ROOT} && source {config.ZSEQUENCER_PROJECT_VIRTUAL_ENV} && uvicorn {proxy_runner_path}:{server_app} --host 0.0.0.0 --port {port} --workers {workers}"


def delete_directory_contents(directory):
    if not os.path.exists(directory):
        return

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")


def launch_node(cmd, env_variables):
    run_command_on_terminal(cmd, env_variables)


def bootstrap_node(node_execution_cmd, proxy_execution_cmd, env_variables):
    run_command_on_terminal(node_execution_cmd, env_variables)
    run_command_on_terminal(proxy_execution_cmd, env_variables)


def generate_transactions(batch_size: int) -> List[Dict]:
    return [
        {
            "operation": "foo",
            "serial": str(uuid4()),
            "version": 6,
        } for _ in range(batch_size)
    ]
