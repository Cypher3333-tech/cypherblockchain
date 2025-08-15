import hashlib
import json
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_dumps(obj: Any) -> str:
    """JSON dump with sorted keys and no spaces for stable hashing/signing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def tx_message(sender: str, recipient: str, amount: int, nonce: int) -> bytes:
    payload = {
        "sender": sender,
        "recipient": recipient,
        "amount": amount,
        "nonce": nonce,
    }
    return deterministic_dumps(payload).encode()


def address_from_pubkey_hex(pubkey_hex: str) -> str:
    """
    Very simple address scheme for demo: address = last 40 hex chars of sha256(pubkey).
    """
    h = sha256(bytes.fromhex(pubkey_hex))
    return h[-40:]