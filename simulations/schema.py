from pydantic import BaseModel
from typing import Any, Dict


class Keys(BaseModel):
    bls_private_key: str
    bls_key_pair: Any
    ecdsa_private_key: str


class KeyData(BaseModel):
    keys: Keys
    address: str


class ExecutionData(BaseModel):
    execution_cmd: str
    env_variables: Dict
