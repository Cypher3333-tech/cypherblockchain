# run_node.py
import os
import json
import time
from flask import Flask, request, render_template_string
from cypher.blockchain import Blockchain, Transaction
from cypher.wallet import Wallet

app = Flask(__name__)

# ------------------- Setup -------------------
NODE_ID = "default-node"
GENESIS_PATH = "config/genesis.json"
chain = Blockchain(node_id=NODE_ID, genesis_path=GENESIS_PATH)

# ------------------- HTML Template -------------------
HTML_PAGE = """
<!doctype html>
<html>
<head>
  <title>Cypher Node</title>
</head>
<body>
  <h1>Cypher Blockchain Node</h1>
  {% if message %}
    <p><b>{{ message }}</b></p>
  {% endif %}

  <h2>Create Wallet</h2>
  <form method="post" action="/create_wallet">
    <button type="submit">New Wallet</button>
  </form>
  {% if new_wallet %}
    <p>Wallet Address: {{ new_wallet }}</p>
  {% endif %}

  <h2>Mine Coins</h2>
  <form method="post" action="/mine">
    <input name="miner" placeholder="Your Wallet Address" value="{{ default_wallet }}">
    <button type="submit">Mine</button>
  </form>
  {% if balance is not none %}
    <p>Balance: {{ balance }}</p>
  {% endif %}

  <h2>Send Coins</h2>
  <form method="post" action="/send">
    <input name="sender" placeholder="Sender Wallet" value="{{ default_wallet }}">
    <input name="recipient" placeholder="Recipient Wallet">
    <input name="amount" placeholder="Amount">
    <button type="submit">Send</button>
  </form>

  <h2>Blockchain</h2>
  <pre>{{ chain_json }}</pre>
</body>
</html>
"""

# ------------------- Routes -------------------
@app.route("/", methods=["GET"])
def index():
    default_wallet = ""
    balance = None
    return render_template_string(
        HTML_PAGE,
        chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2),
        default_wallet=default_wallet,
        balance=balance,
        new_wallet=None,
        message=None
    )

@app.route("/create_wallet", methods=["POST"])
def create_wallet():
    wallet = Wallet()
    return render_template_string(
        HTML_PAGE,
        chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2),
        default_wallet=wallet.address,
        balance=0,
        new_wallet=wallet.address,
        message="✅ Wallet created"
    )

@app.route("/mine", methods=["POST"])
def mine():
    miner = request.form.get("miner")
    if not miner:
        return "Miner address required", 400
    block = chain.mine(miner)
    balances, _ = chain.compute_balances_and_nonces()
    return render_template_string(
        HTML_PAGE,
        chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2),
        default_wallet=miner,
        balance=balances.get(miner, 0),
        new_wallet=None,
        message=f"⛏️ Mined block {block.index}!"
    )

@app.route("/send", methods=["POST"])
def send():
    sender = request.form.get("sender")
    recipient = request.form.get("recipient")
    amount = int(request.form.get("amount", 0))
    
    balances, _ = chain.compute_balances_and_nonces()
    if balances.get(sender, 0) < amount:
        return render_template_string(
            HTML_PAGE,
            chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2),
            default_wallet=sender,
            balance=balances.get(sender, 0),
            new_wallet=None,
            message=f"❌ Insufficient balance ({balances.get(sender,0)})"
        )
    
    tx = Transaction(sender=sender, recipient=recipient, amount=amount, nonce=0)
    chain.current_transactions.append(tx)
    
    # Auto-mine so transaction confirms immediately
    chain.mine(sender)
    
    balances, _ = chain.compute_balances_and_nonces()
    return render_template_string(
        HTML_PAGE,
        chain_json=json.dumps([b.to_dict() for b in chain.chain], indent=2),
        default_wallet=sender,
        balance=balances.get(sender, 0),
        new_wallet=None,
        message=f"✅ Sent {amount} to {recipient}"
    )

# ------------------- Main -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Cypher Node on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
