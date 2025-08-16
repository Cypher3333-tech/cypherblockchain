# cypher/wallet.py
import os
import hashlib
import secrets

DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

class Wallet:
    def __init__(self):
        self.private_key = secrets.token_hex(32)
        self.address = hashlib.sha256(self.private_key.encode()).hexdigest()

    def get_address(self):
        return self.address
