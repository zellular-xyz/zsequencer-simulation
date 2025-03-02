import json
import os
import shutil
from typing import List

from eigensdk.crypto.bls import attestation
from pydantic import BaseModel, Field
from web3 import Account

from simulations.schema import Keys


class SimulationConfig(BaseModel):
    NUM_INSTANCES: int = Field(3, description="Number of instances")
    HOST: str = Field("http://127.0.0.1", description="Host address")
    BASE_PORT: int = Field(6000, description="Base port number")
    PROXY_BASE_PORT: int = Field(7000, description="Base proxy port number")
    THRESHOLD_PERCENT: int = Field(42, description="Threshold percentage")
    DST_DIR: str = Field("/tmp/zellular_dev_net", description="Destination directory")
    HISTORICAL_NODES_REGISTRY_HOST: str = Field("localhost", description="Historical nodes registry host")
    HISTORICAL_NODES_REGISTRY_PORT: int = Field(8000, description="Historical nodes registry port")
    HISTORICAL_NODES_REGISTRY_SOCKET: str = Field(None, description="Socket for historical nodes registry", )
    ZSEQUENCER_SNAPSHOT_CHUNK: int = Field(7000, description="Snapshot chunk size for ZSequencer")
    ZSEQUENCER_REMOVE_CHUNK_BORDER: int = Field(3, description="Chunk border for ZSequencer removal")
    ZSEQUENCER_SEND_BATCH_INTERVAL: float = Field(0.05, description="Interval for sending transactions in ZSequencer")
    ZSEQUENCER_SYNC_INTERVAL: float = Field(0.05, description="Sync interval for ZSequencer")
    ZSEQUENCER_FINALIZATION_TIME_BORDER: int = Field(10, description="Finalization time border for ZSequencer")
    ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT: int = Field(5, description="Timeout for signatures aggregation")
    ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL: int = Field(60, description="Interval to fetch apps and nodes")
    ZSEQUENCER_API_BATCHES_LIMIT: int = Field(5000, description="API batches limit for ZSequencer")
    ZSEQUENCER_NODES_SOURCE: str = Field("file", description="Source for nodes in ZSequencer", )
    APP_NAME: str = Field("simple_app", description="Name of the application")
    TIMESERIES_NODES_COUNT: List[int] = Field([3, 4, 6],
                                              description="count of nodes available on network at different states")
    LOGS_DIRECTORY: str = Field("/tmp/zellular-simulation-logs", description="Directory to store logs")

    class Config:
        validate_assignment = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.HISTORICAL_NODES_REGISTRY_SOCKET = (
            f"{self.HISTORICAL_NODES_REGISTRY_HOST}:{self.HISTORICAL_NODES_REGISTRY_PORT}"
        )

    def get_snapshot_dir(self, node_idx):
        return os.path.join(self.DST_DIR, f'db{node_idx}')

    def get_bls_key_file(self, node_idx):
        return os.path.join(self.DST_DIR, f'bls_key{node_idx}.json')

    @staticmethod
    def get_bls_key_passwd(node_idx):
        return f'a{node_idx}'

    def get_ecdsa_key_file(self, node_idx):
        return os.path.join(self.DST_DIR, f'ecdsa_key{node_idx}.json')

    @staticmethod
    def get_ecdsa_key_passwd(node_idx):
        return f'b{node_idx}'

    def prepare_node(self, node_idx: int, keys: Keys):
        data_dir: str = self.get_snapshot_dir(node_idx=node_idx)
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)

        bls_key_pair: attestation.KeyPair = attestation.new_key_pair_from_string(keys.bls_private_key)
        bls_key_pair.save_to_file(self.get_bls_key_file(node_idx=node_idx), self.get_bls_key_passwd(node_idx))

        encrypted_json = Account.encrypt(keys.ecdsa_private_key, self.get_ecdsa_key_passwd(node_idx))
        with open(self.get_ecdsa_key_file(node_idx), 'w') as f:
            f.write(json.dumps(encrypted_json))

    def to_dict(self, node_idx: int, sequencer_initial_address: str) -> dict:
        return {
            "ZSEQUENCER_APPS_FILE": os.path.join(self.DST_DIR, "apps.json"),
            "ZSEQUENCER_NODES_FILE": os.path.join(self.DST_DIR, "nodes.json"),
            "ZSEQUENCER_HISTORICAL_NODES_REGISTRY": self.HISTORICAL_NODES_REGISTRY_SOCKET,
            "ZSEQUENCER_HOST": "localhost",
            "ZSEQUENCER_PORT": str(self.BASE_PORT + node_idx),
            "ZSEQUENCER_SNAPSHOT_CHUNK": str(self.ZSEQUENCER_SNAPSHOT_CHUNK),
            "ZSEQUENCER_REMOVE_CHUNK_BORDER": str(self.ZSEQUENCER_REMOVE_CHUNK_BORDER),
            "ZSEQUENCER_THRESHOLD_PERCENT": str(self.THRESHOLD_PERCENT),
            "ZSEQUENCER_SEND_BATCH_INTERVAL": str(self.ZSEQUENCER_SEND_BATCH_INTERVAL),
            "ZSEQUENCER_SYNC_INTERVAL": str(self.ZSEQUENCER_SYNC_INTERVAL),
            "ZSEQUENCER_FINALIZATION_TIME_BORDER": str(self.ZSEQUENCER_FINALIZATION_TIME_BORDER),
            "ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT": str(self.ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT),
            "ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL": str(self.ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL),
            "ZSEQUENCER_API_BATCHES_LIMIT": str(self.ZSEQUENCER_API_BATCHES_LIMIT),
            "ZSEQUENCER_INIT_SEQUENCER_ID": sequencer_initial_address,
            "ZSEQUENCER_NODES_SOURCE": self.ZSEQUENCER_NODES_SOURCE,
            # SnapShot Path
            "ZSEQUENCER_SNAPSHOT_PATH": os.path.join(self.DST_DIR, f"db_{node_idx}"),
            # Encryption Files Configs
            "ZSEQUENCER_BLS_KEY_FILE": os.path.join(self.DST_DIR, f"bls_key{node_idx}.json"),
            "ZSEQUENCER_BLS_KEY_PASSWORD": f'a{node_idx}',
            "ZSEQUENCER_ECDSA_KEY_FILE": os.path.join(self.DST_DIR, f"ecdsa_key{node_idx}.json"),
            "ZSEQUENCER_ECDSA_KEY_PASSWORD": f'b{node_idx}',
            # Proxy config
            "ZSEQUENCER_PROXY_HOST": "localhost",
            "ZSEQUENCER_PROXY_PORT": str(self.PROXY_BASE_PORT + node_idx),
            "ZSEQUENCER_PROXY_FLUSH_THRESHOLD_VOLUME": str(2000),
            "ZSEQUENCER_PROXY_FLUSH_THRESHOLD_TIMEOUT": "0.1"
        }
