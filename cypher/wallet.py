# cypher/wallet.py
import os
import secrets
import hashlib

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class Wallet:
    def __init__(self, keyfile: str = None):
        self.data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.keyfile = keyfile or os.path.join(self.data_dir, "wallet.json")
        if os.path.exists(self.keyfile):
            self.load()
        else:
            self.create()

    def create(self):
        self.private_key = secrets.token_hex(32)
        self.public_key = sha256_hex(self.private_key.encode())
        self.address = sha256_hex(self.public_key.encode())[:40]
        self._persist()

    def _persist(self):
        import json
        with open(self.keyfile, "w") as f:
            json.dump({
                "private_key": self.private_key,
                "public_key": self.public_key,
                "address": self.address
            }, f)

    def load(self):
        import json
        with open(self.keyfile, "r") as f:
            data = json.load(f)
        self.private_key = data["private_key"]
        self.public_key = data["public_key"]
        self.address = data["address"]
