import asyncio
import time
import requests
import random

API_URL = "http://127.0.0.1:8000/api/sensor/data"

class MultiIntersectionEnv:
    def __init__(self):
        self.step_count = 0
        self.queues = {
            "A_north": 0, "A_south": 0, "A_east": 0, "A_west": 0,
            "B_north": 0, "B_south": 0, "B_east": 0, "B_west": 0
        }
        self.pedestrians_A = 0
        self.pedestrians_B = 0
        self.emergency_A = None
        self.emergency_B = None
        self.current_rush_hour = "none"

    def generate_traffic(self):
        self.step_count += 1
        
        # Base Traffic Generation
        if self.step_count % 40 < 20:
            self.queues["A_east"] += random.randint(2, 5) 
            self.queues["B_west"] += random.randint(2, 5) 
            self.queues["A_north"] += random.randint(0, 1)
            self.queues["B_north"] += random.randint(0, 1)
        else:
            self.queues["A_north"] += random.randint(1, 3)
            self.queues["B_south"] += random.randint(1, 3)
            self.queues["A_east"] += random.randint(0, 1)
            self.queues["B_west"] += random.randint(0, 1)
            
        # Rush Hour Overrides
        if self.current_rush_hour == "morning":
            # Commuting West into the city
            self.queues["A_east"] += random.randint(3, 7)
            self.queues["B_east"] += random.randint(3, 7)
        elif self.current_rush_hour == "evening":
            # Commuting East out of the city
            self.queues["A_west"] += random.randint(3, 7)
            self.queues["B_west"] += random.randint(3, 7)

        # 3% chance of a pedestrian arriving at crosswalks
        if random.random() < 0.03:
            self.pedestrians_A += random.randint(1, 2)
        if random.random() < 0.03:
            self.pedestrians_B += random.randint(1, 2)
            
        # 1.5% chance of an Ambulance approaching
        self.emergency_A = None
        self.emergency_B = None
        if random.random() < 0.015:
            self.emergency_A = random.choice(["NS", "EW"])
        if random.random() < 0.015:
            self.emergency_B = random.choice(["NS", "EW"])

    def apply_ai_decision(self, action_A: str, action_B: str):
        clear_cap = 12  # Fast clearing rate per phase
        yellow_cap = 2
        
        cleared_A_east = 0
        cleared_B_west = 0
        
        # Intersection A
        if action_A == "GREEN_NS":
            self.queues["A_north"] = max(0, self.queues["A_north"] - clear_cap)
            self.queues["A_south"] = max(0, self.queues["A_south"] - clear_cap)
        elif action_A == "GREEN_EW":
            cleared_A_east = min(clear_cap, self.queues["A_east"])
            self.queues["A_east"] -= cleared_A_east
            self.queues["A_west"] = max(0, self.queues["A_west"] - clear_cap)
        elif action_A == "YELLOW_NS":
            self.queues["A_north"] = max(0, self.queues["A_north"] - yellow_cap)
            self.queues["A_south"] = max(0, self.queues["A_south"] - yellow_cap)
        elif action_A == "YELLOW_EW":
            cleared_A_east = min(yellow_cap, self.queues["A_east"])
            self.queues["A_east"] -= cleared_A_east
            self.queues["A_west"] = max(0, self.queues["A_west"] - yellow_cap)
        elif action_A == "ALL_RED":
            self.pedestrians_A = 0 # Pedestrians cleared

        # Intersection B
        if action_B == "GREEN_NS":
            self.queues["B_north"] = max(0, self.queues["B_north"] - clear_cap)
            self.queues["B_south"] = max(0, self.queues["B_south"] - clear_cap)
        elif action_B == "GREEN_EW":
            self.queues["B_east"] = max(0, self.queues["B_east"] - clear_cap)
            cleared_B_west = min(clear_cap, self.queues["B_west"])
            self.queues["B_west"] -= cleared_B_west
        elif action_B == "YELLOW_NS":
            self.queues["B_north"] = max(0, self.queues["B_north"] - yellow_cap)
            self.queues["B_south"] = max(0, self.queues["B_south"] - yellow_cap)
        elif action_B == "YELLOW_EW":
            self.queues["B_east"] = max(0, self.queues["B_east"] - yellow_cap)
            cleared_B_west = min(yellow_cap, self.queues["B_west"])
            self.queues["B_west"] -= cleared_B_west
        elif action_B == "ALL_RED":
            self.pedestrians_B = 0 # Pedestrians cleared

        # GREEN WAVE PHYSICS (Transfer cars between intersections)
        self.queues["B_east"] += cleared_A_east
        self.queues["A_west"] += cleared_B_west

def run_sensor():
    print("🚦 Multi-Intersection IoT Edge Sensor Started...")
    intersection = MultiIntersectionEnv()
    
    while True:
        intersection.generate_traffic()
        payload = {
            **intersection.queues,
            "pedestrians_A": intersection.pedestrians_A,
            "pedestrians_B": intersection.pedestrians_B,
            "emergency_A": intersection.emergency_A,
            "emergency_B": intersection.emergency_B
        }
        
        try:
            start_time = time.time()
            response = requests.post(API_URL, json=payload, timeout=2.0)
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                action_A = data["ai_decision"]["action_A"]
                action_B = data["ai_decision"]["action_B"]
                intersection.current_rush_hour = data.get("rush_hour", "none")
                
                print(f"[Step {intersection.step_count}] Latency: {latency:.1f}ms | AI Returned: A={action_A}, B={action_B} | Rush: {intersection.current_rush_hour}")
                
                # Apply Decision
                intersection.apply_ai_decision(action_A, action_B)
            else:
                print(f"⚠️ API Error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection failed: {e}. Retrying in 2 seconds...")
            time.sleep(2)
            
        # Run at 1 update per 4.0 seconds (slowed down for realistic observation)
        time.sleep(4.0)

if __name__ == "__main__":
    run_sensor()
