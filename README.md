# 🧠 Synapse City: AI Traffic Control

> **The neural network for urban mobility. Connecting every intersection, clearing every queue.**

Synapse City is an advanced, real-time Smart City Traffic Optimizer. It uses **Deep Q-Network (DQN) Reinforcement Learning** in PyTorch to intelligently manage multi-intersection traffic lights, outperforming standard fixed-timer systems by dynamically adapting to massive traffic surges, emergency vehicles, and pedestrian crossings.

## ✨ Premium Features

- **Reinforcement Learning Core**: Multi-agent DQN model trained using PyTorch and Gymnasium.
- **Glassmorphism Dashboard**: A highly polished, reactive Next.js / TailwindCSS frontend dashboard.
- **Time-of-Day Rush Hour Simulator**: Stress-test the AI by simulating asymmetrical massive influxes of morning commuters or evening traffic.
- **Traffic Incident Simulator**: Trigger car crashes in real-time. Watch the backend identify the blockage, hide it from the AI's state tensor, and proactively reroute cross-traffic to prevent gridlock.
- **Live Carbon Emissions Tracker**: Calculates real-time CO2 emissions saved by the AI reducing idle vehicle time compared to a baseline model.
- **Traffic Density Heatmap**: Dynamic glowing overlays show real-time intersection congestion.
- **Dynamic Weather Engine**: Rain and Fog directly affect physical CSS vehicle speeds and synthesize ambient Web Audio (low-pass filters and white noise generators).

---

## 🚀 Getting Started

### 1. Requirements
- Python 3.10+
- Node.js 18+

### 2. Backend Setup (PyTorch & FastAPI)
Navigate to the root directory, install dependencies, and start the AI Inference Server and IoT Edge Sensor.
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI Backend (WebSocket Server & AI Inference)
python main.py

# In a separate terminal, start the IoT Edge Sensor (Traffic Physics Engine)
python iot_sensor.py
```

### 3. Frontend Setup (Next.js)
Navigate to the `frontend/` directory, install packages, and spin up the dashboard.
```bash
cd frontend
npm install
npm run dev
```
Access the dashboard at **http://localhost:3000**.

---

## 🏗️ Architecture

- **`train_dqn.py`**: The training harness where the agent learns how to manage traffic in a Gymnasium environment.
- **`main.py`**: The production FastAPI server. It loads the compiled `.pth` PyTorch model, exposes endpoints for dashboard controls (Incidents, Rush Hour), and broadcasts live telemetry via WebSockets.
- **`iot_sensor.py`**: The headless physics engine acting as a city IoT network. It generates traffic, pedestrians, and ambulances, and queries `main.py` for light control decisions.
- **`frontend/src/app/page.tsx`**: The massive React component responsible for rendering the entire animated city, decoding WebSocket telemetry, and providing the control UI.

## 📝 License
MIT License
