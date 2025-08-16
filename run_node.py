# run_node.py
import os
import json
from flask import Flask, request, jsonify
from cypher.wallet import Wallet
from cypher.blockchain import Blockchain, DATA_DIR

app = Flask(__name__)

# ------------------ Genesis ------------------
GENESIS_PATH = os.path.join(DATA_DIR, "genesis.json")
if not os.path.exists(GENESIS_PATH):
    genesis = {
        "chain_id":"cypher-mainnet",
        "genesis_time":"2025-08-16T00:00:00Z",
        "initial_difficulty":1,
        "block_reward":50,
        "premine":[{"sender":"GENESIS_FAUCET","recipient":"GENESIS_FAUCET","amount":1000000,"nonce":0}]
    }
    with open(GENESIS_PATH,"w") as f:
        json.dump(genesis,f)

# ------------------ Wallet ------------------
WALLET_FILE = os.path.join(DATA_DIR,"wallet.json")
node_wallet = Wallet(keyfile=WALLET_FILE)

# ------------------ Blockchain ------------------
chain = Blockchain(node_id="render-node", genesis_path=GENESIS_PATH)

# ------------------ API ------------------
@app.route("/health")
def health():
    return {"status":"ok","node_id":chain.node_id}

@app.route("/chain")
def get_chain():
    return {"length": len(chain.chain), "chain":[b.to_dict() for b in chain.chain]}

@app.route("/mine", methods=["GET","POST"])
def mine():
    block = chain.mine(node_wallet.address)
    return {"block": block.to_dict()}

@app.route("/balance/<address>")
def balance(address):
    balances,_ = chain.compute_balances_and_nonces()
    return {"address":address,"balance":balances.get(address,0)}

@app.route("/send", methods=["POST"])
def send():
    data = request.json
    recipient = data.get("to")
    amount = int(data.get("amount",0))
    if chain.new_transaction(node_wallet.address,recipient,amount):
        return {"status":"ok"}
    return {"status":"failed","reason":"insufficient balance"}
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
