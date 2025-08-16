import argparse
import traceback
from flask import Flask, request, jsonify
from cypher.blockchain import Blockchain, Transaction
from cypher.wallet import Wallet

app = Flask(__name__)
chain: Blockchain | None = None
node_wallet: Wallet | None = None

# ---------------------- Routes ----------------------
@app.route("/health", methods=["GET"])
def health():
    if chain is None:
        return {"status": "error", "message": "chain not initialized"}, 500
    return {"status": "ok", "node_id": chain.node_id}, 200

@app.route("/wallet/new", methods=["GET"])
def wallet_new():
    w = Wallet()
    return {"private_key": w.private_key_hex, "public_key": w.public_key_hex, "address": w.address}, 200

@app.route("/wallet/balance/<address>", methods=["GET"])
def wallet_balance(address):
    balances, _ = chain.compute_balances_and_nonces()
    return {"address": address, "balance": balances.get(address, 0)}, 200

@app.route("/tx/pending", methods=["GET"])
def tx_pending():
    return {"pending": [t.to_dict() for t in chain.current_transactions]}, 200

@app.route("/tx/new", methods=["POST"])
def tx_new():
    data = request.get_json(force=True)
    required = ["sender", "recipient", "amount", "nonce"]
    if not all(k in data for k in required):
        return {"error": "missing fields"}, 400
    tx = Transaction(
        sender=data["sender"],
        recipient=data["recipient"],
        amount=int(data["amount"]),
        nonce=int(data["nonce"]),
        pubkey=data.get("pubkey"),
        signature=data.get("signature")
    )
    if chain.new_transaction(tx):
        return {"status": "accepted"}, 201
    return {"status": "rejected"}, 400

@app.route("/mine", methods=["POST", "GET"])
def mine():
    miner = request.args.get("to") or node_wallet.address
    block = chain.mine(miner)
    return {"block": block.to_dict()}, 200

@app.route("/chain", methods=["GET"])
def get_chain():
    return {"length": len(chain.chain), "chain": [b.to_dict() for b in chain.chain]}, 200

@app.route("/nodes/register", methods=["POST"])
def nodes_register():
    data = request.get_json(force=True)
    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        return {"error": "nodes must be a list of URLs like http://host:port"}, 400
    for n in nodes:
        chain.register_node(n)
    return {"ok": True, "nodes": list(chain.nodes)}, 201

@app.route("/nodes/resolve", methods=["GET"])
def nodes_resolve():
    replaced = chain.resolve_conflicts()
    return {"replaced": replaced, "length": len(chain.chain)}, 200

# ---------------------- Main ----------------------
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=5000)
        parser.add_argument("--node-id", dest="node_id", default=None)
        parser.add_argument("--genesis", default="config/genesis.json")
        args = parser.parse_args()

        node_id = args.node_id or str(args.port)
        chain = Blockchain(node_id=node_id, genesis_path=args.genesis)
        node_wallet = Wallet()

        print(f"Starting Cypher node '{node_id}' on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=True, use_reloader=False)

    except Exception:
        traceback.print_exc()
        input("Press Enter to exit...")
