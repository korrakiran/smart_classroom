# Smart Classroom – Federated Learning

A federated learning system where multiple schools collaboratively train a topic-difficulty model **without sharing raw student data**.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FL SERVER (port 6000)             │
│  /register       ← clients register before training │
│  /submit_weights ← clients POST local weights       │
│  /get_global_model → clients GET aggregated model   │
│  /status         → dashboard / debug info           │
│                                                     │
│  FedAvg: averages weights from all clients          │
│  Triggers aggregation once all clients submit       │
└────────────┬──────────────────┬────────────────────┘
             │  HTTP            │  HTTP
    ┌────────▼──────┐   ┌───────▼───────┐
    │  School 1     │   │  School 2     │
    │  train1.py    │   │  train2.py    │
    │  data1.csv ✗──┼───┼──→ (private) │   ← raw data NEVER shared
    └───────────────┘   └───────────────┘

Dashboard (port 5001) reads global_model.csv for visualization + AI chat
```

## How to Run

### 1. Install dependencies
```bash
pip install flask pandas requests python-dotenv
```

### 2. Set up your API key
```bash
cp .env.example .env
# Edit .env and add your Sarvam API key
```

### 3. Generate sample data
```bash
python generate_data.py
```

### 4. Start the FL server (Terminal 1)
```bash
python server/fl_server.py
```

### 5. Run clients in parallel (Terminal 2 & 3)
```bash
# Terminal 2
python clients/school_1/train1.py

# Terminal 3
python clients/school_2/train2.py
```
Each client registers → trains locally → submits weights → server runs FedAvg → global model updated.

### 6. Start the dashboard (Terminal 4)
```bash
python app.py
# Open http://localhost:5001
```

## FL Rounds
- Each client can run multiple rounds: `python clients/school_1/train1.py 3`
- Server auto-aggregates after every round once all clients submit
- Global model improves across rounds

## Key FL Properties
| Property | Implementation |
|---|---|
| No raw data sharing | Only computed weights sent via HTTP |
| Decentralized training | Each school trains on its own data |
| FedAvg aggregation | Server averages weights from all clients |
| Multi-round training | Clients and server iterate across rounds |
| Global model broadcast | Clients receive updated model each round |
