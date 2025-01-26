from typing import List

from pydantic import BaseModel, Field


class SimulationConfig(BaseModel):
    NUM_INSTANCES: int = Field(3, description="Number of instances")
    HOST: str = Field("http://127.0.0.1", description="Host address")
    BASE_PORT: int = Field(6000, description="Base port number")
    THRESHOLD_PERCENT: int = Field(42, description="Threshold percentage")
    DST_DIR: str = Field("/tmp/zellular_dev_net", description="Destination directory")
    APPS_FILE: str = Field("/tmp/zellular_dev_net/apps.json", description="Path to the apps file")
    HISTORICAL_NODES_REGISTRY_HOST: str = Field("localhost", description="Historical nodes registry host")
    HISTORICAL_NODES_REGISTRY_PORT: int = Field(8000, description="Historical nodes registry port")
    HISTORICAL_NODES_REGISTRY_SOCKET: str = Field(
        None,
        description="Socket for historical nodes registry",
    )
    ZSEQUENCER_SNAPSHOT_CHUNK: int = Field(1000, description="Snapshot chunk size for ZSequencer")
    ZSEQUENCER_REMOVE_CHUNK_BORDER: int = Field(3, description="Chunk border for ZSequencer removal")
    ZSEQUENCER_SEND_TXS_INTERVAL: float = Field(0.05, description="Interval for sending transactions in ZSequencer")
    ZSEQUENCER_SYNC_INTERVAL: float = Field(0.05, description="Sync interval for ZSequencer")
    ZSEQUENCER_FINALIZATION_TIME_BORDER: int = Field(10, description="Finalization time border for ZSequencer")
    ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT: int = Field(5, description="Timeout for signatures aggregation")
    ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL: int = Field(60, description="Interval to fetch apps and nodes")
    ZSEQUENCER_API_BATCHES_LIMIT: int = Field(100, description="API batches limit for ZSequencer")
    ZSEQUENCER_NODES_SOURCES: List[str] = Field(
        ["file", "historical_nodes_registry", "eigenlayer"],
        description="Sources for nodes in ZSequencer",
    )
    APP_NAME: str = Field("simple_app", description="Name of the application")
    TIMESERIES_NODES_COUNT: List[int] = Field([3, 4, 6],
                                              description="count of nodes available on network at different states")

    class Config:
        validate_assignment = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.HISTORICAL_NODES_REGISTRY_SOCKET = (
            f"{self.HISTORICAL_NODES_REGISTRY_HOST}:{self.HISTORICAL_NODES_REGISTRY_PORT}"
        )

    def to_dict(self, node_idx: int, sequencer_initial_address: str) -> dict:
        return {
            "ZSEQUENCER_APPS_FILE": self.APPS_FILE,
            "ZSEQUENCER_HISTORICAL_NODES_REGISTRY": self.HISTORICAL_NODES_REGISTRY_SOCKET,
            "ZSEQUENCER_PORT": str(self.BASE_PORT + node_idx),
            "ZSEQUENCER_SNAPSHOT_CHUNK": str(self.ZSEQUENCER_SNAPSHOT_CHUNK),
            "ZSEQUENCER_REMOVE_CHUNK_BORDER": str(self.ZSEQUENCER_REMOVE_CHUNK_BORDER),
            "ZSEQUENCER_THRESHOLD_PERCENT": str(self.THRESHOLD_PERCENT),
            "ZSEQUENCER_SEND_TXS_INTERVAL": str(self.ZSEQUENCER_SEND_TXS_INTERVAL),
            "ZSEQUENCER_SYNC_INTERVAL": str(self.ZSEQUENCER_SYNC_INTERVAL),
            "ZSEQUENCER_FINALIZATION_TIME_BORDER": str(self.ZSEQUENCER_FINALIZATION_TIME_BORDER),
            "ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT": str(self.ZSEQUENCER_SIGNATURES_AGGREGATION_TIMEOUT),
            "ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL": str(self.ZSEQUENCER_FETCH_APPS_AND_NODES_INTERVAL),
            "ZSEQUENCER_API_BATCHES_LIMIT": str(self.ZSEQUENCER_API_BATCHES_LIMIT),
            "ZSEQUENCER_INIT_SEQUENCER_ID": sequencer_initial_address,
            "ZSEQUENCER_NODES_SOURCE": self.ZSEQUENCER_NODES_SOURCES[1]
        }
