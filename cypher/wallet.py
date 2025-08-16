# cypher/wallet.py
import os
import json
import secrets
import hashlib

DATA_DIR = os.environ.get("CYPHER_DATA") or os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class Wallet:
    def __init__(self, keyfile=None):
        self.keyfile = keyfile or os.path.join(DATA_DIR, "wallet.json")
        if os.path.exists(self.keyfile):
            self.load()
        else:
            self.create()

    def create(self):
        self.private_key = secrets.token_hex(32)
        self.address = sha256_hex(self.private_key.encode())[:40]  # simple address
        self.save()

    def save(self):
        data = {"private_key": self.private_key, "address": self.address}
        with open(self.keyfile, "w") as f:
            json.dump(data, f)

    def load(self):
        with open(self.keyfile, "r") as f:
            data = json.load(f)
        self.private_key = data["private_key"]
        self.address = data["address"]
