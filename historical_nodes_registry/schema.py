from pydantic import BaseModel
from typing import Dict


class NodeInfo(BaseModel):
    id: str
    pubkeyG2_X: tuple
    pubkeyG2_Y: tuple
    address: str
    socket: str
    stake: int


SnapShotType = Dict[str, NodeInfo]
