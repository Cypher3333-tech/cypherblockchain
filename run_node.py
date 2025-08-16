# run_node.py
import os
import traceback
from flask import Flask, request, jsonify
from cypher.blockchain import Blockchain, Transaction
from cypher.wallet import Wallet
from typing import Optional

app = Flask(__name__)

# ---------------------- Initialize ----------------------
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

node_wallet = Wallet()
chain: Optional[Blockchain] = None  # will be initialized below

# ---------------------- API ----------------------
@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "node_id": chain.node_id if chain else "not initialized",
        "wallet": node_wallet.get_address()
    }

@app.route("/chain", methods=["GET"])
def get_chain():
    return {
        "length": len(chain.chain),
        "chain": [b.to_dict() for b in chain.chain]
    }

@app.route("/mine", methods=["POST", "GET"])
def mine():
    block = chain.mine(node_wallet.get_address())
    return {"block": block.to_dict()}

@app.route("/balance", methods=["GET"])
def balance():
    balances, _ = chain.compute_balances_and_nonces()
    return {
        "address": node_wallet.get_address(),
        "balance": balances.get(node_wallet.get_address(), 0)
    }

@app.route("/send", methods=["POST"])
def send():
    data = request.json
    recipient = data.get("recipient")
    amount = int(data.get("amount", 0))
    if not recipient or amount <= 0:
        return {"error": "Invalid recipient or amount"}, 400

    # create transaction (ignore signature & nonce for testing)
    tx = Transaction(
        sender=node_wallet.get_address(),
        recipient=recipient,
        amount=amount,
        nonce=0
    )
    # Check balance manually
    balances, _ = chain.compute_balances_and_nonces()
    sender_balance = balances.get(tx.sender, 0)
    if sender_balance < amount:
        return {"error": f"Insufficient balance ({sender_balance})"}, 400

    chain.new_transaction(tx)
    return {"tx": tx.to_dict()}

# ---------------------- Start Node ----------------------
if __name__ == "__main__":
    try:
        node_id = os.environ.get("NODE_ID", "default-node")
        genesis_path = os.environ.get("GENESIS_PATH", "config/genesis.json")

        chain = Blockchain(node_id=node_id, genesis_path=genesis_path)

        port = int(os.environ.get("PORT", 5000))
        print(f"🚀 Starting node '{node_id}' on port {port}")
        print(f"Wallet address: {node_wallet.get_address()}")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    except Exception:
        traceback.print_exc()
