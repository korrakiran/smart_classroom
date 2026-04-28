from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response, session
import pandas as pd
import os
import re
import requests
import pymongo
import bcrypt
import datetime
from functools import wraps
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'super-secret-key-for-sessions')

# MongoDB setup
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
client = pymongo.MongoClient(MONGODB_URL)
db = client["users"]
users = db["email"]
users.create_index("email", unique=True)

# FL MongoDB Setup
fl_clients = db["fl_clients"]
fl_rounds = db["fl_rounds"]
global_model_col = db["global_model"]
fl_metadata = db["fl_metadata"]

if not fl_metadata.find_one({"_id": "metadata"}):
    fl_metadata.insert_one({"_id": "metadata", "current_round": 1, "clients_per_round": 2})

def get_current_round():
    meta = fl_metadata.find_one({"_id": "metadata"})
    return meta["current_round"] if meta else 1

def get_clients_per_round():
    meta = fl_metadata.find_one({"_id": "metadata"})
    return meta["clients_per_round"] if meta else 2

NUMERIC_FIELDS = [
    "weight", "avg_score", "avg_prereq_score", "avg_attempts",
    "avg_time_per_attempt", "avg_hint_usage", "avg_score_variance",
    "avg_sessions", "pct_struggling"
]
CATEGORICAL_FIELDS = ["top_struggle_reason", "top_recommended_action"]

def fedavg(round_updates):
    combined   = {}
    cat_votes  = {}
    total_n    = {}

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


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
@login_required
def dashboard():
    model_docs = list(global_model_col.find({}, {"_id": 0}))
    if model_docs:
        df = pd.DataFrame(model_docs)
        df["class"]  = pd.to_numeric(df["class"],  errors="coerce")
        df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
        df = df.dropna(subset=["class", "subject", "topic", "weight"])
        df["class"] = df["class"].astype(int)

        # Fill optional columns with sensible defaults if missing
        for col in ["avg_score", "avg_prereq_score", "pct_struggling",
                    "avg_hint_usage", "avg_attempts", "avg_time_per_attempt",
                    "top_struggle_reason", "top_recommended_action"]:
            if col not in df.columns:
                df[col] = "N/A" if col in ["top_struggle_reason", "top_recommended_action"] else 0.0

        df = df.drop_duplicates(subset=["class", "subject", "topic"], keep="last")
        data = df.to_dict(orient="records")
    else:
        data = []
    return render_template("dashboard.html", data=data)

@app.route("/login")
def login_page():
    if 'user_email' in session:
        return redirect(url_for('dashboard'))
    return render_template("login.html")

@app.route("/auth/verify", methods=["POST"])
def auth_verify():
    data = request.json
    email = data.get("email")
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
        
    user = users.find_one({"email": email})
    if not user:
        return jsonify({"error": "Email not registered. No signup available."}), 404
        
    needs_password = user.get("password") is None
    return jsonify({"needsPassword": needs_password}), 200

@app.route("/auth/setup_password", methods=["POST"])
def auth_setup_password():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
        
    user = users.find_one({"email": email})
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user.get("password"):
        return jsonify({"error": "Password already set"}), 400
        
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(10)).decode('utf-8')
    users.update_one(
        {"email": email}, 
        {"$set": {
            "password": hashed, 
            "passwordCreatedAt": datetime.datetime.utcnow(),
            "lastLoginAt": datetime.datetime.utcnow(),
            "loginAttempts": 0
        }}
    )
    
    session['user_email'] = email
    return jsonify({"message": "Password created successfully"}), 200

@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
        
    user = users.find_one({"email": email})
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if not user.get("password"):
        return jsonify({"error": "Please setup your password first"}), 400
        
    now = datetime.datetime.utcnow()
    locked_until = user.get("lockedUntil")
    if locked_until and locked_until > now:
        return jsonify({"error": "Account locked", "lockedUntil": True}), 403
        
    if bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
        users.update_one(
            {"email": email}, 
            {"$set": {"lastLoginAt": now, "loginAttempts": 0}, "$unset": {"lockedUntil": ""}}
        )
        
        session['user_email'] = email
        return jsonify({"message": "Login successful"}), 200
    else:
        attempts = user.get("loginAttempts", 0) + 1
        updates = {"loginAttempts": attempts}
        
        if attempts >= 3:
            updates["lockedUntil"] = now + datetime.timedelta(minutes=5)
            users.update_one({"email": email}, {"$set": updates})
            return jsonify({"error": "Too many failed attempts. Please try again in 5 minutes.", "lockedUntil": True}), 403
            
        users.update_one({"email": email}, {"$set": updates})
        return jsonify({"error": "Incorrect password", "attemptsLeft": 3 - attempts}), 401

@app.route("/auth/logout")
def auth_logout():
    session.pop('user_email', None)
    response = make_response(redirect(url_for('login_page')))
    # Prevent browser from caching protected pages
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
    if not SARVAM_API_KEY or SARVAM_API_KEY == "your_sarvam_api_key_here":
        return jsonify({"error": "Sarvam API Key not configured. Please add it to your .env file."}), 500

    user_query   = request.json.get("query")
    context_data = request.json.get("context_data")
    if not user_query:
        return jsonify({"error": "No query provided."}), 400

    system_prompt = f"""You are 'Classroom AI', a friendly and insightful education assistant.

Here is the current classroom data: {context_data}

Engage in a helpful, natural, and extremely brief conversation with the user. 
CRITICAL RULES:
1. NEVER output bulleted lists or long breakdowns.
2. NEVER mention specific percentages or raw data unless explicitly asked.
3. Keep your response to a maximum of 2-3 sentences.
4. Give a high-level, human summary (e.g., "It looks like Class 8 is mostly struggling in Math concepts like Trigonometry and Geometry because they forgot the basics").
5. Do NOT output <think> tags or your internal reasoning process."""

    payload = {
        "model": "sarvam-m",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_query}
        ],
        "temperature": 0.7,
        "top_p": 1,
        "stream": False,
    }

    try:
        response = requests.post(
            "https://api.sarvam.ai/v1/chat/completions",
            headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
            json=payload, timeout=30
        )
        if response.status_code == 401:
            return jsonify({"error": "Invalid API key."}), 401
        if response.status_code != 200:
            return jsonify({"error": f"Sarvam API error {response.status_code}: {response.text}"}), response.status_code

        full_content = response.json()["choices"][0]["message"]["content"]
        full_content = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL).strip()
        return jsonify({"choices": [{"message": {"content": full_content}}]})

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)

# --- Federated Learning Endpoints ---

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    client_id = data.get("client_id")
    name = data.get("name", client_id)
    
    fl_clients.update_one(
        {"client_id": client_id},
        {"$set": {"name": name, "round": 0}},
        upsert=True
    )
    current_round = get_current_round()
    
    model = list(global_model_col.find({}, {"_id": 0}))
    return jsonify({
        "status": "registered",
        "current_round": current_round,
        "global_model": model
    })

@app.route("/submit_weights", methods=["POST"])
def submit_weights():
    data = request.json
    client_id = data.get("client_id")
    round_num = data.get("round")
    weights = data.get("weights")
    
    fl_rounds.update_one(
        {"round_num": round_num},
        {"$set": {f"updates.{client_id}": weights}},
        upsert=True
    )
    
    fl_clients.update_one(
        {"client_id": client_id},
        {"$set": {"round": round_num}}
    )
    
    round_doc = fl_rounds.find_one({"round_num": round_num})
    updates = round_doc.get("updates", {})
    received = len(updates)
    clients_needed = get_clients_per_round()
    
    aggregated = False
    if received >= clients_needed:
        if not round_doc.get("aggregated"):
            new_model_dict = fedavg(updates)
            
            for key, entry in new_model_dict.items():
                global_model_col.update_one(
                    {"class": entry["class"], "subject": entry["subject"], "topic": entry["topic"]},
                    {"$set": entry},
                    upsert=True
                )
            
            fl_rounds.update_one({"round_num": round_num}, {"$set": {"aggregated": True}})
            fl_metadata.update_one({"_id": "metadata"}, {"$inc": {"current_round": 1}})
            aggregated = True
        else:
            aggregated = True
            
    return jsonify({
        "status": "received",
        "aggregated": aggregated,
        "clients_submitted": received,
        "clients_needed": clients_needed
    })

@app.route("/get_global_model", methods=["GET"])
def get_global_model():
    model = list(global_model_col.find({}, {"_id": 0}))
    return jsonify({"round": get_current_round(), "global_model": model})

@app.route("/status", methods=["GET"])
def status():
    clients = {c["client_id"]: {"name": c.get("name"), "round": c.get("round")} for c in fl_clients.find()}
    model_size = global_model_col.count_documents({})
    current_round = get_current_round()
    return jsonify({
        "current_round": current_round,
        "registered_clients": clients,
        "rounds_completed": current_round - 1,
        "global_model_size": model_size
    })
