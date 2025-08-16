# cypher/blockchain.py
from __future__ import annotations
import time
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
import requests
from .utils import sha256, deterministic_dumps
from .wallet import verify_signature, Wallet

DATA_DIR = os.environ.get("CYPHER_DATA", ".cypher_data")


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    nonce: int
    pubkey: Optional[str] = None
    signature: Optional[str] = None

    def is_coinbase(self) -> bool:
        return self.sender in ("COINBASE", "GENESIS_FAUCET")

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[Dict]
    previous_hash: str
    nonce: int
    difficulty: int

    def to_dict(self) -> Dict:
        return asdict(self)


class Blockchain:
    def __init__(self, node_id: str, genesis_path: str):
        self.node_id = node_id
        self.current_transactions: List[Transaction] = []
        self.chain: List[Block] = []
        self.nodes: Set[str] = set()

        os.makedirs(DATA_DIR, exist_ok=True)
        self.db_path = os.path.join(DATA_DIR, f"chain_{self.node_id}.json")

        if os.path.exists(self.db_path):
            self._load()
        else:
            with open(genesis_path, "r", encoding="utf-8") as f:
                self.genesis = json.load(f)
            self._create_genesis_block()
            self._persist()

    # ---------------------- Genesis Block ----------------------
    def _create_genesis_block(self):
        premine_txs = [
            Transaction(
                sender=t.get("sender", "GENESIS_FAUCET"),
                recipient=t.get("recipient", "GENESIS_FAUCET"),
                amount=int(t["amount"]),
                nonce=int(t.get("nonce", 0))
            ) for t in self.genesis.get("premine", [])
        ]
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[tx.to_dict() for tx in premine_txs],
            previous_hash="0" * 64,
            nonce=0,
            difficulty=self.genesis.get("initial_difficulty", 1)
        )
        self.chain.append(genesis_block)

    # ---------------------- Persistence ----------------------
    def _persist(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def _load(self):
        with open(self.db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chain = [Block(**b) for b in data]
        # minimal genesis info
        self.genesis = {
            "initial_difficulty": self.chain[0].difficulty,
            "block_reward": 50,
            "premine": [],
        }

    # ---------------------- Core Helpers ----------------------
    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def hash_block(self, block: Block) -> str:
        content = deterministic_dumps(block.to_dict()).encode()
        return sha256(content)

    def proof_of_work(self, difficulty: int, base: Dict) -> int:
        nonce = 0
        prefix = "0" * difficulty
        while True:
            candidate = deterministic_dumps({**base, "nonce": nonce}).encode()
            h = sha256(candidate)
            if h.startswith(prefix):
                return nonce
            nonce += 1

    # ---------------------- State ----------------------
    def compute_balances_and_nonces(self) -> (Dict[str, int], Dict[str, int]):
        balances: Dict[str, int] = {}
        nonces: Dict[str, int] = {}

        for block in self.chain:
            for tx in block.transactions:
                sender = tx["sender"]
                recipient = tx["recipient"]
                amount = int(tx["amount"])
                nonce = int(tx["nonce"])

                if sender != "COINBASE" and sender != "GENESIS_FAUCET":
                    balances[sender] = balances.get(sender, 0) - amount
                    nonces[sender] = max(nonces.get(sender, 0), nonce + 1)
                balances[recipient] = balances.get(recipient, 0) + amount

        return balances, nonces

    # ---------------------- Validation ----------------------
    def validate_transaction(self, tx: Transaction) -> bool:
        if tx.is_coinbase():
            return True

        if not (tx.pubkey and tx.signature):
            return False

        if not verify_signature(tx.pubkey, tx.signature, tx.sender, tx.recipient, tx.amount, tx.nonce):
            return False

        from .utils import address_from_pubkey_hex
        if address_from_pubkey_hex(tx.pubkey) != tx.sender:
            return False

        balances, nonces = self.compute_balances_and_nonces()
        balance = balances.get(tx.sender, 0)
        expected_nonce = nonces.get(tx.sender, 0)

        if tx.amount <= 0 or balance < tx.amount or tx.nonce != expected_nonce:
            return False
        return True

    def validate_block(self, block: Block, previous_block: Optional[Block]) -> bool:
        if previous_block:
            if block.previous_hash != self.hash_block(previous_block):
                return False
            if block.index != previous_block.index + 1:
                return False
        # Check PoW
        content = {k: getattr(block, k) for k in ("index", "timestamp", "transactions", "previous_hash", "difficulty")}
        prefix = "0" * block.difficulty
        h = sha256(deterministic_dumps({**content, "nonce": block.nonce}).encode())
        if not h.startswith(prefix):
            return False
        for tx in [Transaction(**t) for t in block.transactions]:
            if not self.validate_transaction(tx):
                return False
        return True

    def validate_chain(self, chain: List[Block]) -> bool:
        for i, blk in enumerate(chain):
            prev = chain[i - 1] if i > 0 else None
            if not self.validate_block(blk, prev):
                return False
        return True

    # ---------------------- Block/Tx Management ----------------------
    def new_transaction(self, tx: Transaction) -> bool:
        if self.validate_transaction(tx):
            self.current_transactions.append(tx)
            return True
        return False

    def mine(self, miner_address: str) -> Block:
        difficulty = min(5, (self.last_block.difficulty + 1) if (self.last_block.index % 10 == 0) else self.last_block.difficulty)

        reward_tx = Transaction(sender="COINBASE", recipient=miner_address, amount=self.genesis.get("block_reward", 50), nonce=0)
        txs = [reward_tx.to_dict()] + [t.to_dict() for t in self.current_transactions]

        base = {
            "index": self.last_block.index + 1,
            "timestamp": time.time(),
            "transactions": txs,
            "previous_hash": self.hash_block(self.last_block),
            "difficulty": difficulty,
        }
        nonce = self.proof_of_work(difficulty, base)

        block = Block(**{**base, "nonce": nonce})
        if not self.validate_block(block, self.last_block):
            raise ValueError("mined invalid block")

        self.chain.append(block)
        self.current_transactions = []
        self._persist()
        return block

    # ---------------------- Networking ----------------------
    def register_node(self, address: str):
        self.nodes.add(address)

    def resolve_conflicts(self) -> bool:
        longest = self.chain
        replaced = False

        for node in list(self.nodes):
            try:
                res = requests.get(f"{node}/chain", timeout=3)
                if res.ok:
                    data = res.json()
                    remote_chain = [Block(**b) for b in data.get("chain", [])]
                    if len(remote_chain) > len(longest) and self.validate_chain(remote_chain):
                        longest = remote_chain
                        replaced = True
            except Exception:
                continue

        if replaced:
            self.chain = longest
            self._persist()
        return replaced
