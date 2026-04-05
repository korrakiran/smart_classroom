"""
Federated Learning Server (Upgraded)
- Receives rich weight updates (difficulty + struggle_reason + recommended_action)
- FedAvg: weighted average on numeric fields
- Majority vote on categorical fields (struggle_reason, recommended_action)
- Saves enriched global_model.csv for dashboard
"""

from flask import Flask, request, jsonify
import pandas as pd
import os
import threading

app = Flask(__name__)

REGISTERED_CLIENTS  = {}
ROUND_UPDATES       = {}
GLOBAL_MODEL        = {}       # key: (class, subject, topic) → dict of fields
CURRENT_ROUND       = 1
CLIENTS_PER_ROUND   = 2
lock                = threading.Lock()

GLOBAL_MODEL_PATH = os.path.join(os.path.dirname(__file__), "global_model.csv")

NUMERIC_FIELDS = [
    "weight", "avg_score", "avg_prereq_score", "avg_attempts",
    "avg_time_per_attempt", "avg_hint_usage", "avg_score_variance",
    "avg_sessions", "pct_struggling"
]
CATEGORICAL_FIELDS = ["top_struggle_reason", "top_recommended_action"]

# ── Persistence ───────────────────────────────────────────────────────────────
def load_global_model():
    global GLOBAL_MODEL
    if os.path.exists(GLOBAL_MODEL_PATH):
        df = pd.read_csv(GLOBAL_MODEL_PATH)
        for _, row in df.iterrows():
            key = (int(row["class"]), row["subject"], row["topic"])
            GLOBAL_MODEL[key] = row.to_dict()

def save_global_model():
    rows = list(GLOBAL_MODEL.values())
    if rows:
        df = pd.DataFrame(rows).sort_values(["class", "subject", "topic"])
        df.to_csv(GLOBAL_MODEL_PATH, index=False)

# ── FedAvg (upgraded) ─────────────────────────────────────────────────────────
def fedavg(round_updates):
    """
    Weighted FedAvg on numeric fields.
    Majority vote (weighted by n_samples) on categorical fields.
    """
    combined   = {}   # key → {field → weighted_sum}
    cat_votes  = {}   # key → {field → {value → total_n}}
    total_n    = {}   # key → total n_samples

    for client_id, weights in round_updates.items():
        for w in weights:
            key = (w["class"], w["subject"], w["topic"])
            n   = w.get("n_samples", 1)

            if key not in combined:
                combined[key]  = {f: 0.0 for f in NUMERIC_FIELDS}
                cat_votes[key] = {f: {} for f in CATEGORICAL_FIELDS}
                total_n[key]   = 0

            total_n[key] += n
            for f in NUMERIC_FIELDS:
                combined[key][f] += w.get(f, 0.0) * n
            for f in CATEGORICAL_FIELDS:
                val = w.get(f, "unknown")
                cat_votes[key][f][val] = cat_votes[key][f].get(val, 0) + n

    result = {}
    for key in combined:
        n = total_n[key]
        entry = {
            "class":   key[0],
            "subject": key[1],
            "topic":   key[2],
        }
        for f in NUMERIC_FIELDS:
            entry[f] = round(combined[key][f] / n, 4) if n > 0 else 0.0
        for f in CATEGORICAL_FIELDS:
            votes = cat_votes[key][f]
            entry[f] = max(votes, key=votes.get) if votes else "unknown"
        result[key] = entry

    return result

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/register", methods=["POST"])
def register():
    data      = request.json
    client_id = data.get("client_id")
    name      = data.get("name", client_id)
    with lock:
        REGISTERED_CLIENTS[client_id] = {"name": name, "round": 0}
    print(f"[Server] Registered: {name}")
    return jsonify({
        "status": "registered",
        "current_round": CURRENT_ROUND,
        "global_model": list(GLOBAL_MODEL.values())
    })

@app.route("/submit_weights", methods=["POST"])
def submit_weights():
    global CURRENT_ROUND, GLOBAL_MODEL
    data      = request.json
    client_id = data.get("client_id")
    round_num = data.get("round")
    weights   = data.get("weights")

    with lock:
        if round_num not in ROUND_UPDATES:
            ROUND_UPDATES[round_num] = {}
        ROUND_UPDATES[round_num][client_id] = weights
        REGISTERED_CLIENTS[client_id]["round"] = round_num
        received = len(ROUND_UPDATES[round_num])
        print(f"[Server] Round {round_num}: {client_id} submitted ({received}/{CLIENTS_PER_ROUND})")

        if received >= CLIENTS_PER_ROUND:
            print(f"[Server] All clients in. Running FedAvg...")
            GLOBAL_MODEL  = fedavg(ROUND_UPDATES[round_num])
            save_global_model()
            CURRENT_ROUND = round_num + 1
            print(f"[Server] Global model updated. Next round: {CURRENT_ROUND}")
            aggregated = True
        else:
            aggregated = False

    return jsonify({
        "status": "received",
        "aggregated": aggregated,
        "clients_submitted": received,
        "clients_needed": CLIENTS_PER_ROUND
    })

@app.route("/get_global_model", methods=["GET"])
def get_global_model():
    with lock:
        model = list(GLOBAL_MODEL.values())
    return jsonify({"round": CURRENT_ROUND, "global_model": model})

@app.route("/status", methods=["GET"])
def status():
    with lock:
        return jsonify({
            "current_round":      CURRENT_ROUND,
            "registered_clients": REGISTERED_CLIENTS,
            "rounds_completed":   CURRENT_ROUND - 1,
            "global_model_size":  len(GLOBAL_MODEL)
        })

if __name__ == "__main__":
    load_global_model()
    print(f"[Server] FL Server starting on port 6000. Round {CURRENT_ROUND}.")
    app.run(port=6000, debug=False)
