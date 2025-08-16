# run_node.py
import os
import json
import time
from flask import Flask, request, jsonify
from cypher.blockchain import Blockchain, Transaction
from cypher.wallet import Wallet

app = Flask(__name__)

DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Auto-generate genesis.json if missing
GENESIS_PATH = os.path.join(DATA_DIR, "genesis.json")
if not os.path.exists(GENESIS_PATH):
    genesis = {
        "chain_id": "cypher-mainnet",
        "genesis_time": "2025-08-16T00:00:00Z",
        "initial_difficulty": 1,
        "block_reward": 50,
        "premine": [
            {"sender": "GENESIS_FAUCET", "recipient": "GENESIS_FAUCET", "amount": 1000000, "nonce": 0}
        ]
    }
    with open(GENESIS_PATH, "w") as f:
        json.dump(genesis, f)

# Initialize blockchain and wallet
NODE_ID = os.environ.get("NODE_ID", "default-node")
chain = Blockchain(node_id=NODE_ID, genesis_path=GENESIS_PATH)
wallet = Wallet()

# ------------------- API -------------------
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "node_id": NODE_ID}, 200

@app.route("/wallet", methods=["GET"])
def get_wallet():
    return {
        "address": wallet.address,
        "public_key": wallet.public_key,
        "private_key": wallet.private_key
    }, 200

@app.route("/balance", methods=["GET"])
def get_balance():
    balances, _ = chain.compute_balances_and_nonces()
    balance = balances.get(wallet.address, 0)
    return {"address": wallet.address, "balance": balance}, 200

@app.route("/mine", methods=["POST", "GET"])
def mine():
    block = chain.mine(wallet.address)
    return {"block": block.to_dict()}, 200

@app.route("/send", methods=["POST"])
def send():
    data = request.json
    recipient = data.get("recipient")
    amount = int(data.get("amount", 0))
    if not recipient or amount <= 0:
        return {"error": "invalid recipient or amount"}, 400

    # naive transaction (no signature/nonce required)
    tx = Transaction(sender=wallet.address, recipient=recipient, amount=amount, nonce=0)
    success = chain.new_transaction(tx)
    if not success:
        return {"error": "insufficient balance"}, 400
    return {"status": "ok", "tx": tx.to_dict()}, 200

@app.route("/chain", methods=["GET"])
def get_chain():
    return {"length": len(chain.chain), "chain": [b.to_dict() for b in chain.chain]}, 200

# ------------------- Run -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
