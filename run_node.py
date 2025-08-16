import os
import time
import traceback
from flask import Flask, request, jsonify, render_template_string
from cypher.blockchain import Blockchain, Transaction
from cypher.wallet import Wallet

app = Flask(__name__)
chain: Blockchain | None = None
wallets: dict[str, Wallet] = {}  # store wallets


# ------------------- HTML Dashboard -------------------
HTML_TEMPLATE = """
<!doctype html>
<title>Cypher Node Dashboard</title>
<h1>Cypher Node {{ node_id }}</h1>
<h2>Create Wallet</h2>
<form action="/wallet" method="post">
    <button>Create Wallet</button>
</form>

<h2>Mine</h2>
<form action="/mine" method="post">
    <input name="to" placeholder="Wallet address" required>
    <button>Mine</button>
</form>

<h2>Check Balance</h2>
<form action="/balance" method="get">
    <input name="address" placeholder="Wallet address" required>
    <button>Check Balance</button>
</form>

<h2>Send Coins</h2>
<form action="/send" method="post">
    <input name="sender" placeholder="Sender address" required><br>
    <input name="recipient" placeholder="Recipient address" required><br>
    <input name="amount" type="number" placeholder="Amount" required><br>
    <button>Send</button>
</form>
<hr>
<a href="/chain">View Full Chain</a>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE, node_id=chain.node_id)


# ------------------- Wallet -------------------
@app.route("/wallet", methods=["POST"])
def create_wallet():
    wallet = Wallet()
    wallets[wallet.address] = wallet
    return jsonify({
        "address": wallet.address,
        "public_key": wallet.pubkey,
        "private_key": wallet.privkey
    })


# ------------------- Mine -------------------
@app.route("/mine", methods=["POST"])
def mine():
    miner_address = request.form.get("to")
    if not miner_address:
        return {"error": "Provide wallet address"}, 400
    block = chain.mine(miner_address)
    return jsonify({"block": block.to_dict()})


# ------------------- Balance -------------------
@app.route("/balance", methods=["GET"])
def get_balance_form():
    address = request.args.get("address")
    if not address:
        return {"error": "Provide wallet address"}, 400
    balances, _ = chain.compute_balances_and_nonces()
    return jsonify({"address": address, "balance": balances.get(address, 0)})


# ------------------- Send Coins -------------------
@app.route("/send", methods=["POST"])
def send_coins():
    sender = request.form.get("sender")
    recipient = request.form.get("recipient")
    amount = int(request.form.get("amount", 0))

    if not sender or not recipient or amount <= 0:
        return {"error": "sender, recipient, amount required"}, 400

    tx = Transaction(sender=sender, recipient=recipient, amount=amount, nonce=0)
    if chain.new_transaction(tx):
        return jsonify({"status": "ok", "tx": tx.to_dict()})
    return {"error": "transaction invalid or insufficient balance"}, 400


# ------------------- Chain -------------------
@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify({"length": len(chain.chain), "chain": [b.to_dict() for b in chain.chain]})


# ------------------- Health -------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "node_id": chain.node_id})


# ------------------- Main -------------------
if __name__ == "__main__":
    try:
        node_id = os.environ.get("NODE_ID", "default-node")
        genesis_path = os.environ.get("GENESIS_PATH", "config/genesis.json")

        chain = Blockchain(node_id=node_id, genesis_path=genesis_path)

        port = int(os.environ.get("PORT", 5000))
        print(f"🚀 Starting Cypher Node '{node_id}' on port {port}")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    except Exception:
        traceback.print_exc()
