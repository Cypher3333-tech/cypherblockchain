import os
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Dict
from flask import Flask, request, jsonify, render_template_string
import hashlib
import secrets

# ---------------- Utils ----------------
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def deterministic_dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

# ---------------- Wallet ----------------
class Wallet:
    def __init__(self):
        self.privkey = secrets.token_hex(32)
        self.pubkey = secrets.token_hex(64)
        self.address = sha256(self.pubkey.encode())[:40]

# ---------------- Models ----------------
@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int

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

# ---------------- Blockchain ----------------
class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.current_transactions: List[Transaction] = []
        self._create_genesis_block()

    def _create_genesis_block(self):
        genesis_tx = Transaction(sender="GENESIS_FAUCET", recipient="GENESIS_FAUCET", amount=1_000_000_000)
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[genesis_tx.to_dict()],
            previous_hash="0"*64,
            nonce=0,
            difficulty=2
        )
        self.chain.append(genesis_block)

    @property
    def last_block(self):
        return self.chain[-1]

    def compute_balances(self) -> Dict[str,int]:
        balances = {}
        for block in self.chain:
            for tx in block.transactions:
                balances[tx["sender"]] = balances.get(tx["sender"],0) - tx["amount"] if tx["sender"] not in ("COINBASE","GENESIS_FAUCET") else balances.get(tx["sender"],0)
                balances[tx["recipient"]] = balances.get(tx["recipient"],0) + tx["amount"]
        return balances

    def new_transaction(self, tx: Transaction) -> bool:
        balances = self.compute_balances()
        if balances.get(tx.sender,0) < tx.amount and tx.sender not in ("COINBASE","GENESIS_FAUCET"):
            return False
        self.current_transactions.append(tx)
        return True

    def proof_of_work(self, base):
        nonce = 0
        prefix = "0"*base["difficulty"]
        while True:
            candidate = dict(base)
            candidate["nonce"] = nonce
            h = sha256(deterministic_dumps(candidate).encode())
            if h.startswith(prefix):
                return nonce
            nonce += 1

    def mine(self, miner_address):
        reward_tx = Transaction(sender="COINBASE", recipient=miner_address, amount=50)
        txs = [reward_tx.to_dict()] + [t.to_dict() for t in self.current_transactions]
        base = {
            "index": self.last_block.index+1,
            "timestamp": time.time(),
            "transactions": txs,
            "previous_hash": sha256(deterministic_dumps(self.last_block.to_dict()).encode()),
            "difficulty": max(2,self.last_block.difficulty)
        }
        nonce = self.proof_of_work(base)
        block = Block(**base, nonce=nonce)
        self.chain.append(block)
        self.current_transactions = []
        return block

# ---------------- Flask App ----------------
app = Flask(__name__)
chain = Blockchain()
wallets: Dict[str, Wallet] = {}

# ---------------- HTML Template ----------------
HTML_PAGE = """
<!doctype html>
<html>
<head>
<title>Cypher Node</title>
<style>
body { font-family: sans-serif; margin: 20px; }
input, button { margin:5px 0; padding:5px; }
</style>
</head>
<body>
<h1>Cypher Node</h1>

<h2>Create Wallet</h2>
<form method="post" action="/wallet/create">
<button type="submit">Create Wallet</button>
</form>

<h2>Mine Coins</h2>
<form method="post" action="/mine">
Wallet Address: <input name="miner" value="{{ default_wallet }}"><br>
<button type="submit">Mine</button>
</form>

<h2>Send Coins</h2>
<form method="post" action="/send">
Sender: <input name="sender"><br>
Recipient: <input name="recipient"><br>
Amount: <input name="amount" type="number"><br>
<button type="submit">Send</button>
</form>

<h2>Check Balance</h2>
<form method="get" action="/balance">
Address: <input name="address" value="{{ default_wallet }}"><br>
<button type="submit">Check Balance</button>
</form>

<h2>Blockchain</h2>
<pre>{{ chain_json }}</pre>
</body>
</html>
"""

# ---------------- Routes ----------------
@app.route("/", methods=["GET"])
def index():
    default_wallet = list(wallets.keys())[0] if wallets else ""
    return render_template_string(HTML_PAGE, chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2), default_wallet=default_wallet)

@app.route("/wallet/create", methods=["POST"])
def create_wallet():
    wallet = Wallet()
    wallets[wallet.address] = wallet
    return render_template_string(HTML_PAGE, chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2), default_wallet=wallet.address)

@app.route("/mine", methods=["POST"])
def mine():
    miner = request.form.get("miner")
    if miner not in wallets:
        return "Wallet not found",400
    chain.mine(miner)
    return render_template_string(HTML_PAGE, chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2), default_wallet=miner)

@app.route("/send", methods=["POST"])
def send():
    sender = request.form.get("sender")
    recipient = request.form.get("recipient")
    amount = int(request.form.get("amount",0))
    if sender not in wallets:
        return "Sender wallet not found",400
    tx = Transaction(sender=sender, recipient=recipient, amount=amount)
    if chain.new_transaction(tx):
        return render_template_string(HTML_PAGE, chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2), default_wallet=sender)
    else:
        return "Insufficient balance",400

@app.route("/balance", methods=["GET"])
def balance():
    address = request.args.get("address")
    if not address:
        return "Address required",400
    balances = chain.compute_balances()
    bal = balances.get(address,0)
    return render_template_string(HTML_PAGE, chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2), default_wallet=address)

# ---------------- Main ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    print(f"Starting Cypher Node on port {port}")
    app.run(host="0.0.0.0", port=port)
