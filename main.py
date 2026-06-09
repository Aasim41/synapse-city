from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import numpy as np
import torch
import torch.nn as nn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PyTorch DQN Model ---
class TrafficDQN(nn.Module):
    def __init__(self, state_size=8, action_size=4):
        super(TrafficDQN, self).__init__()
        self.fc1 = nn.Linear(state_size, 128)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(128, 128)
        self.relu2 = nn.ReLU()
        self.out = nn.Linear(128, action_size)

    def forward(self, x):
        x = self.relu1(self.fc1(x))
        x = self.relu2(self.fc2(x))
        return self.out(x)

policy_net = TrafficDQN(8, 4)
try:
    policy_net.load_state_dict(torch.load("traffic_dqn_multi.pth", map_location=torch.device('cpu'), weights_only=True))
    policy_net.eval()
    print("✅ Loaded PyTorch Multi-Agent DQN model!")
except Exception as e:
    print(f"⚠️ Could not load PyTorch model: {e}. Falling back to random actions.")

# --- Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.dashboard_clients: List[WebSocket] = []

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_clients.append(websocket)

    def disconnect_dashboard(self, websocket: WebSocket):
        self.dashboard_clients.remove(websocket)

    async def broadcast_traffic(self, data: dict):
        for connection in self.dashboard_clients:
            try:
                await connection.send_json(data)
            except:
                pass

manager = ConnectionManager()

# --- Traffic Phase Controller (Multi-Agent) ---
class MultiTrafficController:
    def __init__(self):
        self.phase_A = "GREEN_NS"
        self.phase_B = "GREEN_NS"
        self.yellow_A = 0
        self.yellow_B = 0
        self.green_A_ticks = 0
        self.green_B_ticks = 0
        self.YELLOW_DURATION = 1
        self.MIN_GREEN_DURATION = 3

    def update(self, desired_A: str, desired_B: str):
        # Intersection A logic
        if self.yellow_A > 0:
            self.yellow_A -= 1
            if self.yellow_A == 0:
                self.phase_A = desired_A
                self.green_A_ticks = 0
        else:
            if self.phase_A != desired_A:
                if self.phase_A == "ALL_RED":
                    self.phase_A = desired_A
                    self.green_A_ticks = 0
                # Allow switch if min duration met OR if it's an emergency/pedestrian
                elif self.green_A_ticks >= self.MIN_GREEN_DURATION or "ALL_RED" in desired_A:
                    self.phase_A = "YELLOW"
                    self.yellow_A = self.YELLOW_DURATION
                else:
                    self.green_A_ticks += 1
            else:
                self.green_A_ticks += 1
                
        # Intersection B logic
        if self.yellow_B > 0:
            self.yellow_B -= 1
            if self.yellow_B == 0:
                self.phase_B = desired_B
                self.green_B_ticks = 0
        else:
            if self.phase_B != desired_B:
                if self.phase_B == "ALL_RED":
                    self.phase_B = desired_B
                    self.green_B_ticks = 0
                elif self.green_B_ticks >= self.MIN_GREEN_DURATION or "ALL_RED" in desired_B:
                    self.phase_B = "YELLOW"
                    self.yellow_B = self.YELLOW_DURATION
                else:
                    self.green_B_ticks += 1
            else:
                self.green_B_ticks += 1
                
        # Format actual string
        if self.phase_A == "ALL_RED":
            actual_A = "ALL_RED"
        else:
            actual_A = self.phase_A if self.phase_A != "YELLOW" else ("YELLOW_NS" if desired_A == "GREEN_EW" or desired_A == "ALL_RED" else "YELLOW_EW")
            
        if self.phase_B == "ALL_RED":
            actual_B = "ALL_RED"
        else:
            actual_B = self.phase_B if self.phase_B != "YELLOW" else ("YELLOW_NS" if desired_B == "GREEN_EW" or desired_B == "ALL_RED" else "YELLOW_EW")
            
        return actual_A, actual_B

traffic_controller = MultiTrafficController()

# --- Endpoints ---
@app.get("/")
def read_root():
    return {"status": "Smart City Multi-Agent Backend running"}

active_incident = None
active_rush_hour = "none"

@app.post("/api/incident")
async def trigger_incident(payload: dict):
    global active_incident
    loc = payload.get("location")
    active_incident = loc if loc != "none" else None
    return {"status": "success", "active_incident": active_incident}

@app.post("/api/rush_hour")
async def trigger_rush_hour(payload: dict):
    global active_rush_hour
    active_rush_hour = payload.get("mode", "none")
    return {"status": "success", "active_rush_hour": active_rush_hour}

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)

@app.post("/api/sensor/data")
async def receive_sensor_data(payload: dict):
    global active_incident
    
    # 1. Force the visual queue to show the jam if there is an incident
    if active_incident and active_incident in payload:
        payload[active_incident] = 45
        
    state = [
        payload.get("A_north", 0), payload.get("A_south", 0), payload.get("A_east", 0), payload.get("A_west", 0),
        payload.get("B_north", 0), payload.get("B_south", 0), payload.get("B_east", 0), payload.get("B_west", 0)
    ]
    
    # 2. Hide the incident from the AI so it routes cross-traffic instead of getting stuck
    ai_state = state.copy()
    if active_incident:
        idx = ["A_north", "A_south", "A_east", "A_west", "B_north", "B_south", "B_east", "B_west"].index(active_incident)
        ai_state[idx] = 0
    
    # AI INFERENCE
    s_array = np.array(ai_state, dtype=np.float32)
    s_scaled = s_array / 50.0
    s_tensor = torch.FloatTensor(s_scaled).unsqueeze(0)
    
    try:
        with torch.no_grad():
            q_values = policy_net(s_tensor)
            ai_action = int(torch.argmax(q_values).item())
    except:
        ai_action = 0
        
    desired_A = "GREEN_NS" if ai_action in [0, 1] else "GREEN_EW"
    desired_B = "GREEN_NS" if ai_action in [0, 2] else "GREEN_EW"
    
    # Base AI reason
    if active_incident and active_incident.startswith("A"):
        xai_A = f"⚠️ INCIDENT DETECTED on {active_incident}! Isolating lane and prioritizing cross-traffic."
    else:
        xai_A = f"AI chose {desired_A.replace('GREEN_', '')} to keep traffic moving smoothly."
        
    if active_incident and active_incident.startswith("B"):
        xai_B = f"⚠️ INCIDENT DETECTED on {active_incident}! Isolating lane and prioritizing cross-traffic."
    else:
        xai_B = f"AI chose {desired_B.replace('GREEN_', '')} to keep traffic moving smoothly."

    # --- HYBRID SAFETY OVERRIDE ---
    A_ns_total = state[0] + state[1]
    A_ew_total = state[2] + state[3]
    B_ns_total = state[4] + state[5]
    B_ew_total = state[6] + state[7]

    OVERRIDE_THRESHOLD = 15

    # 1. Vehicle Override
    if A_ns_total > A_ew_total + OVERRIDE_THRESHOLD:
        desired_A = "GREEN_NS"
        xai_A = f"Traffic jam detected! Giving Green to North-South to clear {A_ns_total} cars."
    elif A_ew_total > A_ns_total + OVERRIDE_THRESHOLD:
        desired_A = "GREEN_EW"
        xai_A = f"Traffic jam detected! Giving Green to East-West to clear {A_ew_total} cars."
        
    if B_ns_total > B_ew_total + OVERRIDE_THRESHOLD:
        desired_B = "GREEN_NS"
        xai_B = f"Traffic jam detected! Giving Green to North-South to clear {B_ns_total} cars."
    elif B_ew_total > B_ns_total + OVERRIDE_THRESHOLD:
        desired_B = "GREEN_EW"
        xai_B = f"Traffic jam detected! Giving Green to East-West to clear {B_ew_total} cars."

    # 2. Pedestrian Hardware Interrupt (Highest Priority)
    pedestrians_A = payload.get("pedestrians_A", 0)
    pedestrians_B = payload.get("pedestrians_B", 0)
    
    if pedestrians_A > 0:
        desired_A = "ALL_RED"
        xai_A = "Pedestrian crossing! Stopping all traffic for safety."
        
    if pedestrians_B > 0:
        desired_B = "ALL_RED"
        xai_B = "Pedestrian crossing! Stopping all traffic for safety."
        
    # 3. Emergency GPS Override (Ultimate Priority)
    emergency_A = payload.get("emergency_A", None)
    emergency_B = payload.get("emergency_B", None)
    
    if emergency_A or emergency_B:
        desired_A = "ALL_RED"
        desired_B = "ALL_RED"
        if emergency_A:
            xai_A = f"🚨 EMERGENCY OVERRIDE: Ambulance approaching {emergency_A}! Stopping all traffic for emergency clearance."
            xai_B = f"🚨 EMERGENCY OVERRIDE: Stopping traffic for ambulance at Intersection A."
        if emergency_B:
            xai_A = f"🚨 EMERGENCY OVERRIDE: Stopping traffic for ambulance at Intersection B."
            xai_B = f"🚨 EMERGENCY OVERRIDE: Ambulance approaching {emergency_B}! Stopping all traffic for emergency clearance."
        if emergency_A and emergency_B:
            xai_A = f"🚨 EMERGENCY OVERRIDE: Ambulance approaching {emergency_A}! Stopping all traffic."
            xai_B = f"🚨 EMERGENCY OVERRIDE: Ambulance approaching {emergency_B}! Stopping all traffic."
            
    phase_A, phase_B = traffic_controller.update(desired_A, desired_B)
    
    response_data = {
        "queues": payload,
        "action": ai_action,
        "action_name": "MULTI_AGENT",
        "action_A": phase_A,
        "action_B": phase_B,
        "xai_A": xai_A,
        "xai_B": xai_B,
        "emergency_A": emergency_A,
        "emergency_B": emergency_B,
        "active_incident": active_incident,
        "rush_hour": active_rush_hour
    }
    await manager.broadcast_traffic(response_data)
    return {"status": "success", "ai_decision": response_data, "rush_hour": active_rush_hour}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
