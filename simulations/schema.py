from pydantic import BaseModel
from typing import Any


class Keys(BaseModel):
    bls_private_key: str
    bls_key_pair: Any
    ecdsa_private_key: str
