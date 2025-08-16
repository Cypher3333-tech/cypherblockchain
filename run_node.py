# run_node.py
import os
import time
from flask import Flask, request, jsonify
from cypher.blockchain import Blockchain, Transaction
from cypher.wallet import Wallet

app = Flask(__name__)

# ------------------ Setup ------------------
NODE_ID = os.environ.get("NODE_ID", "default-node")
GENESIS_PATH = os.environ.get("GENESIS_PATH", "config/genesis.json")
PORT = int(os.environ.get("PORT", 5000))

chain = Blockchain(node_id=NODE_ID, genesis_path=GENESIS_PATH)
node_wallet = Wallet()  # miner wallet

# ------------------ API ------------------
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "node_id": chain.node_id}, 200

@app.route("/chain", methods=["GET"])
def get_chain():
    return {
        "length": len(chain.chain),
        "chain": [b.to_dict() for b in chain.chain]
    }, 200

@app.route("/mine", methods=["POST", "GET"])
def mine():
    miner = request.args.get("to") or node_wallet.address
    block = chain.mine(miner)
    return {"block": block.to_dict()}, 200

@app.route("/balance/<address>", methods=["GET"])
def get_balance(address):
    balances, _ = chain.compute_balances_and_nonces()
    return {"address": address, "balance": balances.get(address, 0)}, 200

@app.route("/send", methods=["POST"])
def send_tx():
    data = request.json
    sender = data.get("sender")
    recipient = data.get("recipient")
    amount = int(data.get("amount", 0))

    if not sender or not recipient or amount <= 0:
        return {"error": "sender, recipient, and positive amount required"}, 400

    # Dev-mode transaction: ignore signature and nonce
    tx = Transaction(sender=sender, recipient=recipient, amount=amount, nonce=0)
    chain.current_transactions.append(tx)
    return {"status": "ok", "tx": tx.to_dict()}, 200

# ------------------ Main ------------------
if __name__ == "__main__":
    print(f"🚀 Starting Cypher Node '{NODE_ID}' on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
