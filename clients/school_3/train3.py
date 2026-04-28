"""
Federated Learning Client – School 3 (Upgraded)
Trains locally on rich dataset: computes per-topic
  difficulty_score, dominant struggle_reason,
  top recommended_action, and n_samples.
Only these aggregated weights leave the school.
"""

import pandas as pd
import requests
import os
import sys

SERVER_URL  = "https://smart-classroom-nine.vercel.app"
CLIENT_ID   = "school_3"
CLIENT_NAME = "School 3 - Bangalore"
DATA_PATH   = os.path.join(os.path.dirname(__file__), "data3.csv")

def load_and_train():
    print(f"[{CLIENT_NAME}] Loading local data...")
    df = pd.read_csv(DATA_PATH)

    grouped = df.groupby(["class", "subject", "topic"])
    weights = []

    for (cls, subject, topic), g in grouped:
        n = len(g)
        avg_difficulty   = round(g["difficulty_score"].mean(), 4)
        avg_prereq       = round(g["prerequisite_score"].mean(), 2)
        avg_score        = round(g["score"].mean(), 2)
        avg_attempts     = round(g["num_attempts"].mean(), 2)
        avg_time         = round(g["avg_time_per_attempt"].mean(), 2)
        avg_hint         = round(g["hint_usage_count"].mean(), 2)
        avg_variance     = round(g["score_variance"].mean(), 2)
        avg_sessions     = round(g["session_count"].mean(), 2)

        struggling = g[g["struggle_reason"] != "none"]
        if len(struggling) > 0:
            top_reason = struggling["struggle_reason"].value_counts().idxmax()
            top_action = struggling["recommended_action"].value_counts().idxmax()
            pct_struggling = round(len(struggling) / n * 100, 1)
        else:
            top_reason = "none"
            top_action = "maintain_current_pace"
            pct_struggling = 0.0

        weights.append({
            "class":              int(cls),
            "subject":            subject,
            "topic":              topic,
            "n_samples":          n,
            "weight":             avg_difficulty,
            "avg_score":          avg_score,
            "avg_prereq_score":   avg_prereq,
            "avg_attempts":       avg_attempts,
            "avg_time_per_attempt": avg_time,
            "avg_hint_usage":     avg_hint,
            "avg_score_variance": avg_variance,
            "avg_sessions":       avg_sessions,
            "pct_struggling":     pct_struggling,
            "top_struggle_reason": top_reason,
            "top_recommended_action": top_action,
        })

    print(f"[{CLIENT_NAME}] Training complete. {len(weights)} topic weights computed.")
    return weights

def run(num_rounds=3):
    print(f"[{CLIENT_NAME}] Registering with FL server...")
    try:
        resp = requests.post(f"{SERVER_URL}/register",
                             json={"client_id": CLIENT_ID, "name": CLIENT_NAME}, timeout=5)
        data = resp.json()
        print(f"[{CLIENT_NAME}] Registered. Server is on round {data['current_round']}.")
        start_round = data["current_round"]
    except Exception as e:
        print(f"[{CLIENT_NAME}] Could not reach server: {e}")
        sys.exit(1)

    for round_num in range(start_round, start_round + num_rounds):
        print(f"\n[{CLIENT_NAME}] ── Round {round_num} ──")
        local_weights = load_and_train()

        resp   = requests.post(f"{SERVER_URL}/submit_weights",
                               json={"client_id": CLIENT_ID, "round": round_num,
                                     "weights": local_weights}, timeout=10)
        result = resp.json()
        print(f"[{CLIENT_NAME}] {result['clients_submitted']}/{result['clients_needed']} clients submitted.")

        if result["aggregated"]:
            print(f"[{CLIENT_NAME}] Global model aggregated!")
            gm = requests.get(f"{SERVER_URL}/get_global_model", timeout=5).json()
            print(f"[{CLIENT_NAME}] Global model has {len(gm['global_model'])} topic entries.")
        else:
            print(f"[{CLIENT_NAME}] Waiting for other clients...")

    print(f"\n[{CLIENT_NAME}] Done. {num_rounds} round(s) complete.")

if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(rounds)
