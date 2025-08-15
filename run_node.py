import os
import traceback
from cypher.blockchain import Blockchain
from cypher.wallet import Wallet
from flask import Flask, request, jsonify

app = Flask(__name__)
chain: Blockchain | None = None
node_wallet: Wallet | None = None

# ------------------- API -------------------
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "node_id": chain.node_id}, 200


@app.route("/chain", methods=["GET"])
def get_chain():
    return {"length": len(chain.chain), "chain": [b.to_dict() for b in chain.chain]}, 200


@app.route("/mine", methods=["POST", "GET"])
def mine():
    miner = request.args.get("to") or node_wallet.address
    block = chain.mine(miner)
    return {"block": block.to_dict()}, 200


# ------------------- Main -------------------
if __name__ == "__main__":
    try:
        node_id = os.environ.get("NODE_ID", "default-node")
        genesis_path = os.environ.get("GENESIS_PATH", "config/genesis.json")

        chain = Blockchain(node_id=node_id, genesis_path=genesis_path)
        node_wallet = Wallet()

        # ✅ Use PORT from environment (important for cloud hosts)
        port = int(os.environ.get("PORT", 5000))

        print(f"🚀 Starting Cypher Node '{node_id}' on port {port}")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    except Exception:
        traceback.print_exc()

