"""
Standalone re-aggregation script (kept for compatibility).
In normal operation, fl_server.py handles aggregation automatically.
Run this only to manually re-aggregate from global_model.csv.
"""

import pandas as pd
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "global_model.csv")

if os.path.exists(MODEL_PATH):
    df = pd.read_csv(MODEL_PATH)
    numeric_cols = ["weight", "avg_score", "avg_prereq_score", "avg_attempts",
                    "avg_time_per_attempt", "avg_hint_usage", "avg_score_variance",
                    "avg_sessions", "pct_struggling"]
    existing_numeric = [c for c in numeric_cols if c in df.columns]
    agg = df.groupby(["class", "subject", "topic"])[existing_numeric].mean().reset_index()
    agg = agg.sort_values(["class", "subject", "topic"])
    agg.to_csv(MODEL_PATH, index=False)
    print(f"Re-aggregated global model: {len(agg)} entries saved.")
else:
    print("No global_model.csv found. Run FL training first.")
