# cypher/blockchain.py
import os
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import hashlib

DATA_DIR = os.environ.get("CYPHER_DATA") or os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    nonce: int = 0

    def to_dict(self):
        return asdict(self)

@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[Dict]
    previous_hash: str
    nonce: int
    difficulty: int

    def to_dict(self):
        return asdict(self)

class Blockchain:
    def __init__(self, node_id: str, genesis_path: str):
        self.node_id = node_id
        self.current_transactions: List[Transaction] = []
        self.chain: List[Block] = []

        self.db_path = os.path.join(DATA_DIR, f"chain_{self.node_id}.json")
        if os.path.exists(self.db_path):
            self._load()
        else:
            with open(genesis_path, "r") as f:
                self.genesis = json.load(f)
            self._create_genesis_block()
            self._persist()

    def _create_genesis_block(self):
        premine = self.genesis.get("premine", [])
        txs = [Transaction(**t).to_dict() for t in premine]
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=txs,
            previous_hash="0"*64,
            nonce=0,
            difficulty=int(self.genesis.get("initial_difficulty", 1))
        )
        self.chain.append(genesis_block)

    def _persist(self):
        with open(self.db_path, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def _load(self):
        with open(self.db_path, "r") as f:
            data = json.load(f)
        self.chain = [Block(**b) for b in data]

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, difficulty: int, base: Dict) -> int:
        nonce = 0
        prefix = "0" * difficulty
        while True:
            candidate = json.dumps({**base, "nonce": nonce}, sort_keys=True).encode()
            h = sha256(candidate)
            if h.startswith(prefix):
                return nonce
            nonce += 1

    def compute_balances_and_nonces(self) -> Tuple[Dict[str,int], Dict[str,int]]:
        balances: Dict[str,int] = {}
        nonces: Dict[str,int] = {}
        for block in self.chain:
            for tx in block.transactions:
                sender = tx["sender"]
                recipient = tx["recipient"]
                amount = int(tx["amount"])
                balances[sender] = balances.get(sender,0) - amount if sender not in ["COINBASE","GENESIS_FAUCET"] else balances.get(sender,0)
                balances[recipient] = balances.get(recipient,0) + amount
        return balances, nonces

    def new_transaction(self, sender, recipient, amount) -> bool:
        balances, _ = self.compute_balances_and_nonces()
        if sender not in ["COINBASE","GENESIS_FAUCET"] and balances.get(sender,0) < amount:
            return False
        tx = Transaction(sender, recipient, amount)
        self.current_transactions.append(tx)
        return True

    def mine(self, miner_address: str):
        reward_tx = Transaction("COINBASE", miner_address, int(self.genesis.get("block_reward",50)))
        txs = [reward_tx.to_dict()] + [tx.to_dict() for tx in self.current_transactions]
        base = {
            "index": self.last_block.index + 1,
            "timestamp": time.time(),
            "transactions": txs,
            "previous_hash": sha256(json.dumps(self.last_block.to_dict(),sort_keys=True).encode()),
            "difficulty": int(self.last_block.difficulty)
        }
        nonce = self.proof_of_work(int(base["difficulty"]), base)
        block = Block(**{**base, "nonce": nonce})
        self.chain.append(block)
        self.current_transactions = []
        self._persist()
        return block

