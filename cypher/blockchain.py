# cypher/blockchain.py
from __future__ import annotations
import os
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set, Tuple
import requests

# utils & wallet helpers (already in your project)
from .utils import sha256, deterministic_dumps, address_from_pubkey_hex
from .wallet import verify_signature

# -------- Storage (Render-friendly) --------
# Uses ./data by default; override with env CYPHER_DATA if you want.
DATA_DIR = os.environ.get("CYPHER_DATA") or os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)


# ===================== Models =====================
@dataclass
class Transaction:
    sender: str                 # address, or "COINBASE"/"GENESIS_FAUCET"
    recipient: str              # address
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
    transactions: List[Dict]     # list of tx dicts
    previous_hash: str
    nonce: int
    difficulty: int

    def to_dict(self) -> Dict:
        return asdict(self)


# ===================== Blockchain =====================
class Blockchain:
    def __init__(self, node_id: str, genesis_path: str):
        self.node_id = node_id
        self.current_transactions: List[Transaction] = []
        self.chain: List[Block] = []
        self.nodes: Set[str] = set()

        self.db_path = os.path.join(DATA_DIR, f"chain_{self.node_id}.json")

        if os.path.exists(self.db_path):
            self._load()
        else:
            with open(genesis_path, "r", encoding="utf-8") as f:
                self.genesis = json.load(f)
            self._create_genesis_block()
            self._persist()

    # -------- Genesis --------
    def _create_genesis_block(self) -> None:
        """
        genesis.json expected shape (examples):
        {
          "chain_id": "cypher-mainnet",
          "genesis_time": "2025-08-14T00:00:00Z",
          "initial_difficulty": 4,
          "block_reward": 50,
          "premine": [
            {"recipient": "GENESIS_FAUCET", "amount": 1000000}
          ]
        }
        """
        premine_src = self.genesis.get("premine", [])

        premine_txs: List[Transaction] = []
        for item in premine_src:
            # Allow several field aliases for convenience
            recipient = item.get("recipient") or item.get("address") or "GENESIS_FAUCET"
            amount = int(item.get("amount", 0))
            premine_txs.append(Transaction(
                sender="GENESIS_FAUCET",
                recipient=recipient,
                amount=amount,
                nonce=0
            ))

        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[tx.to_dict() for tx in premine_txs],
            previous_hash="0" * 64,
            nonce=0,
            difficulty=int(self.genesis.get("initial_difficulty", 1)),
        )
        self.chain.append(genesis_block)

    # -------- Persistence --------
    def _persist(self) -> None:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def _load(self) -> None:
        with open(self.db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.chain = [Block(**b) for b in data]
        # reconstruct minimal genesis fallback
        if self.chain:
            self.genesis = {
                "initial_difficulty": int(self.chain[0].difficulty),
                "block_reward": int(self.genesis.get("block_reward", 50)) if hasattr(self, "genesis") else 50,
                "premine": [],
            }
        else:
            # Shouldn't happen, but guard anyway
            self.genesis = {"initial_difficulty": 1, "block_reward": 50, "premine": []}

    # -------- Helpers --------
    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def hash_block(self, block: Block) -> str:
        content = deterministic_dumps(block.to_dict()).encode()
        return sha256(content)

    def proof_of_work(self, difficulty: int, base: Dict) -> int:
        prefix = "0" * int(difficulty)
        nonce = 0
        while True:
            candidate = deterministic_dumps({**base, "nonce": nonce}).encode()
            h = sha256(candidate)
            if h.startswith(prefix):
                return nonce
            nonce += 1

    # -------- State --------
    def compute_balances_and_nonces(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        balances: Dict[str, int] = {}
        nonces: Dict[str, int] = {}

        for block in self.chain:
            for tx in block.transactions:
                sender = tx["sender"]
                recipient = tx["recipient"]
                amount = int(tx["amount"])
                nonce = int(tx["nonce"])

                if sender not in ("COINBASE", "GENESIS_FAUCET"):
                    balances[sender] = balances.get(sender, 0) - amount
                    nonces[sender] = max(nonces.get(sender, 0), nonce + 1)

                balances[recipient] = balances.get(recipient, 0) + amount

        return balances, nonces

    # -------- Validation --------
    def validate_transaction(self, tx: Transaction) -> bool:
        # Coinbase/faucet bypasses signature & balance checks
        if tx.is_coinbase():
            return True

        # Signature presence
        if not (tx.pubkey and tx.signature):
            return False

        # Signature must validate payload
        if not verify_signature(tx.pubkey, tx.signature, tx.sender, tx.recipient, tx.amount, tx.nonce):
            return False

        # Address must match pubkey
        if address_from_pubkey_hex(tx.pubkey) != tx.sender:
            return False

        balances, nonces = self.compute_balances_and_nonces()
        balance = int(balances.get(tx.sender, 0))
        expected_nonce = int(nonces.get(tx.sender, 0))

        if tx.amount <= 0:
            return False
        if balance < tx.amount:
            return False
        if tx.nonce != expected_nonce:
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
        prefix = "0" * int(block.difficulty)
        h = sha256(deterministic_dumps({**content, "nonce": block.nonce}).encode())
        if not h.startswith(prefix):
            return False

        # Check transactions
        for t in block.transactions:
            if not self.validate_transaction(Transaction(**t)):
                return False

        return True

    def validate_chain(self, chain: List[Block]) -> bool:
        for i, blk in enumerate(chain):
            prev = chain[i - 1] if i > 0 else None
            if not self.validate_block(blk, prev):
                return False
        return True

    # -------- Tx / Mining --------
    def new_transaction(self, tx: Transaction) -> bool:
        if self.validate_transaction(tx):
            self.current_transactions.append(tx)
            return True
        return False

    def mine(self, miner_address: str) -> Block:
        # naive difficulty bump every 10 blocks up to 5
        prev = self.last_block
        difficulty = min(5, (prev.difficulty + 1) if (prev.index % 10 == 0 and prev.index != 0) else prev.difficulty)

        # coinbase reward
        reward_tx = Transaction(
            sender="COINBASE",
            recipient=miner_address,
            amount=int(self.genesis.get("block_reward", 50)),
            nonce=0
        )

        txs = [reward_tx.to_dict()] + [t.to_dict() for t in self.current_transactions]

        base = {
            "index": prev.index + 1,
            "timestamp": time.time(),
            "transactions": txs,
            "previous_hash": self.hash_block(prev),
            "difficulty": int(difficulty),
        }
        nonce = self.proof_of_work(int(difficulty), base)
        block = Block(**{**base, "nonce": nonce})

        if not self.validate_block(block, prev):
            raise ValueError("mined invalid block")

        self.chain.append(block)
        self.current_transactions = []
        self._persist()
        return block

    # -------- Networking --------
    def register_node(self, address: str) -> None:
        # address like "http://host:port"
        if isinstance(address, str) and address.strip():
            self.nodes.add(address.strip())

    def resolve_conflicts(self) -> bool:
        """Naive longest-chain consensus with validation."""
        longest = self.chain
        replaced = False

        for node in list(self.nodes):
            try:
                res = requests.get(f"{node}/chain", timeout=4)
                if not res.ok:
                    continue
                data = res.json()
                remote = [Block(**b) for b in data.get("chain", [])]
                if len(remote) > len(longest) and self.validate_chain(remote):
                    longest = remote
                    replaced = True
            except Exception:
                # ignore unreachable nodes/timeouts
                continue

        if replaced:
            self.chain = longest
            self._persist()
        return replaced

