# cypher/wallet.py
import os
import json
import secrets
from hashlib import sha256

DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def random_hex(n=32) -> str:
    return secrets.token_hex(n)

class Wallet:
    def __init__(self, filename=None):
        self.filename = filename or os.path.join(DATA_DIR, "wallet.json")
        self.address = None
        self.private_key = None
        self.load_or_create()

    def load_or_create(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                data = json.load(f)
                self.address = data.get("address")
                self.private_key = data.get("private_key")
        else:
            self.private_key = random_hex(32)
            self.address = sha256(self.private_key.encode()).hexdigest()[:40]
            with open(self.filename, "w") as f:
                json.dump({"address": self.address, "private_key": self.private_key}, f)

    def get_address(self) -> str:
        return self.address
