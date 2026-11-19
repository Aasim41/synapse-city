"""
Synapse City - Indian City Traffic Vision Sensor (YOLOv8 + OpenCV)
Feeds live real-world vehicle detection counts to the Synapse City AI Controller.
"""

import sys
import time
import argparse
import threading
import requests
import cv2
import numpy as np
from ultralytics import YOLO

# --- PCU (Passenger Car Unit) Standards for Indian Traffic (IRC) ---
PCU_WEIGHTS = {
    "motorcycle": 0.5,
    "car": 1.0,
    "bus": 3.0,
    "truck": 3.0,
    "person": 0.0  # Used for pedestrian safety override
}

TARGET_CLASSES = set(PCU_WEIGHTS.keys())

class IndianTrafficVisionSensor:
    def __init__(self, video_path="assets/indian_traffic.mp4", api_url="http://127.0.0.1:8000/api/sensor/data", show_display=True):
        self.video_path = video_path
        self.api_url = api_url
        self.show_display = show_display
        
        print("🧠 Loading YOLOv8 nano model for real-time edge inference...")
        self.model = YOLO("yolov8n.pt")
        
        # State variables
        self.latest_decision = {
            "action_A": "GREEN_NS",
            "action_B": "GREEN_NS",
            "xai_A": "Awaiting initial AI decision...",
            "xai_B": ""
        }
        self.current_queues = {
            "A_north": 0, "A_south": 0, "A_east": 0, "A_west": 0,
            "B_north": 2, "B_south": 2, "B_east": 4, "B_west": 3,
            "pedestrians_A": 0, "pedestrians_B": 0,
            "emergency_A": None, "emergency_B": None
        }
        self.zone_counts_detail = {k: {} for k in ["A_north", "A_south", "A_east", "A_west"]}
        
        self.emergency_trigger = None
        self.pedestrian_trigger = 0
        self.show_zones = True
        self.paused = False
        self.running = True
        self.lock = threading.Lock()
        
        # Background worker for sending sensor telemetry without blocking video loop
        self.api_thread = threading.Thread(target=self._api_worker, daemon=True)
        self.api_thread.start()

    def _api_worker(self):
        """Continuously sends real detected queues to Synapse City FastAPI backend."""
        while self.running:
            with self.lock:
                payload = dict(self.current_queues)
                if self.emergency_trigger:
                    payload["emergency_A"] = self.emergency_trigger
                if self.pedestrian_trigger > 0:
                    payload["pedestrians_A"] = self.pedestrian_trigger
            
            try:
                start = time.time()
                resp = requests.post(self.api_url, json=payload, timeout=1.5)
                latency = (time.time() - start) * 1000
                if resp.status_code == 200:
                    data = resp.json().get("ai_decision", {})
                    with self.lock:
                        self.latest_decision = data
                        self.latest_decision["latency"] = latency
            except Exception as e:
                # Backend might still be starting or busy
                pass
                
            time.sleep(1.0)  # Telemetry update rate: 1 Hz

    def get_zones(self, width, height):
        """
        Defines 4 directional approach zones for an intersection view:
        North (Top), South (Bottom), East (Right), West (Left).
        """
        w, h = width, height
        cx, cy = w // 2, h // 2
        
        zones = {
            "A_north": np.array([[w * 0.25, 0], [w * 0.75, 0], [w * 0.65, cy], [w * 0.35, cy]], np.int32),
            "A_south": np.array([[w * 0.30, cy], [w * 0.70, cy], [w * 0.85, h], [w * 0.15, h]], np.int32),
            "A_west":  np.array([[0, h * 0.25], [w * 0.35, cy], [w * 0.30, h * 0.8], [0, h * 0.85]], np.int32),
            "A_east":  np.array([[w * 0.65, cy], [w, h * 0.25], [w, h * 0.85], [w * 0.70, h * 0.8]], np.int32),
        }
        return zones

    def run(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"❌ Error: Could not open video source: {self.video_path}")
            return
            
        print("\n" + "="*60)
        print("🚦 Synapse City Indian Traffic Vision Sensor Active!")
        print("🎮 Controls:")
        print("   [P] - Trigger Pedestrian Crossing (Safety Override)")
        print("   [E] - Trigger Approaching Ambulance (ALL-RED Override)")
        print("   [Z] - Toggle Detection Zones Overlay")
        print("   [Space] - Pause / Resume Video")
        print("   [Q] - Quit")
        print("="*60 + "\n")
        
        frame_count = 0
        
        while self.running:
            if not self.paused:
                ret, frame = cap.read()
                if not ret:
                    # Seamlessly loop the video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                frame_count += 1
            else:
                time.sleep(0.03)
                continue
                
            h, w = frame.shape[:2]
            zones = self.get_zones(w, h)
            
            # Run YOLO detection every 2 frames for silky smooth FPS
            results = self.model(frame, verbose=False, conf=0.25)[0]
            
            # Temporary counters
            zone_pcu = {"A_north": 0.0, "A_south": 0.0, "A_east": 0.0, "A_west": 0.0}
            zone_details = {k: {"car": 0, "bike": 0, "heavy": 0} for k in zone_pcu}
            pedestrians_found = 0
            
            # Draw detections
            for box in results.boxes:
                cls_id = int(box.cls[0].item())
                label = self.model.names[cls_id]
                
                if label not in TARGET_CLASSES:
                    continue
                    
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                
                if label == "person":
                    pedestrians_found += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
                    continue
                
                pcu = PCU_WEIGHTS.get(label, 1.0)
                
                # Check which zone this vehicle is in
                in_zone = None
                for z_name, poly in zones.items():
                    if cv2.pointPolygonTest(poly, (cx, cy), False) >= 0:
                        zone_pcu[z_name] += pcu
                        in_zone = z_name
                        if label == "motorcycle":
                            zone_details[z_name]["bike"] += 1
                        elif label in ["bus", "truck"]:
                            zone_details[z_name]["heavy"] += 1
                        else:
                            zone_details[z_name]["car"] += 1
                        break
                        
                # Visual styling based on vehicle type
                if label == "motorcycle":
                    color = (0, 255, 255)  # Yellow for 2-wheelers
                    tag = f"Bike ({pcu} PCU)"
                elif label in ["bus", "truck"]:
                    color = (0, 140, 255)  # Orange for Heavy vehicles
                    tag = f"{label.capitalize()} ({pcu} PCU)"
                else:
                    color = (255, 200, 0)  # Cyan for Cars/Autos
                    tag = f"Car ({pcu} PCU)"
                    
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(frame, (cx, cy), 4, color, -1)
                cv2.putText(frame, tag, (x1, max(y1 - 6, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

            # Update shared state
            with self.lock:
                self.current_queues["A_north"] = int(np.ceil(zone_pcu["A_north"]))
                self.current_queues["A_south"] = int(np.ceil(zone_pcu["A_south"]))
                self.current_queues["A_east"]  = int(np.ceil(zone_pcu["A_east"]))
                self.current_queues["A_west"]  = int(np.ceil(zone_pcu["A_west"]))
                # If pedestrians detected in footage, feed it
                if pedestrians_found > 0:
                    self.current_queues["pedestrians_A"] = pedestrians_found
                self.zone_counts_detail = zone_details

            # --- HUD & AI OVERLAYS ---
            overlay = frame.copy()
            
            # 1. Draw detection zone polygons
            if self.show_zones:
                zone_colors = {
                    "A_north": (0, 165, 255),
                    "A_south": (0, 255, 0),
                    "A_west":  (255, 0, 128),
                    "A_east":  (255, 255, 0)
                }
                for z_name, poly in zones.items():
                    cv2.polylines(overlay, [poly], isClosed=True, color=zone_colors[z_name], thickness=2)
                    cv2.fillPoly(overlay, [poly], color=zone_colors[z_name])
                # Alpha blend zones (20% opacity)
                cv2.addWeighted(overlay, 0.20, frame, 0.80, 0, frame)

            # 2. Draw HUD Header
            cv2.rectangle(frame, (0, 0), (w, 90), (15, 18, 25), -1)
            cv2.line(frame, (0, 90), (w, 90), (45, 55, 72), 2)
            
            # Title & Telemetry
            cv2.putText(frame, "SYNAPSE CITY - INDIAN TRAFFIC VISION SENSOR", (20, 28), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
            
            with self.lock:
                dec = self.latest_decision
                action_A = dec.get("action_A", "GREEN_NS")
                xai_A = dec.get("xai_A", "")
                lat = dec.get("latency", 0.0)
                
            # Traffic Signal Status Badge
            if "ALL_RED" in action_A:
                ns_color, ew_color = (0, 0, 255), (0, 0, 255)
                badge_text = "ALL-RED [EMERGENCY / SAFETY OVERRIDE]"
                badge_bg = (0, 0, 200)
            elif "GREEN_NS" in action_A:
                ns_color, ew_color = (0, 255, 0), (0, 0, 255)
                badge_text = "GREEN WAVE: NORTH-SOUTH"
                badge_bg = (0, 160, 0)
            elif "YELLOW_NS" in action_A:
                ns_color, ew_color = (0, 255, 255), (0, 0, 255)
                badge_text = "PHASE TRANSITION: YELLOW (NS)"
                badge_bg = (0, 180, 220)
            elif "GREEN_EW" in action_A:
                ns_color, ew_color = (0, 0, 255), (0, 255, 0)
                badge_text = "GREEN WAVE: EAST-WEST"
                badge_bg = (0, 160, 0)
            else:
                ns_color, ew_color = (0, 0, 255), (0, 255, 255)
                badge_text = "PHASE TRANSITION: YELLOW (EW)"
                badge_bg = (0, 180, 220)
                
            # Draw Signal Lights Indicators
            cv2.circle(frame, (w - 180, 30), 10, ns_color, -1)
            cv2.putText(frame, "NS Signal", (w - 160, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
            
            cv2.circle(frame, (w - 70, 30), 10, ew_color, -1)
            cv2.putText(frame, "EW Signal", (w - 50, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
            
            # Badge text
            cv2.rectangle(frame, (20, 42), (480, 72), badge_bg, -1, cv2.LINE_AA)
            cv2.putText(frame, badge_text, (30, 63), cv2.FONT_HERSHEY_DUPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
            
            # XAI Explanation String
            cv2.putText(frame, f"AI Reasoning: {xai_A} ({lat:.1f}ms latency)", (20, 83), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 190, 205), 1, cv2.LINE_AA)
            
            # 3. Zone PCU Density Summary Table (Bottom HUD)
            cv2.rectangle(frame, (0, h - 55), (w, h), (15, 18, 25), -1)
            cv2.line(frame, (0, h - 55), (w, h - 55), (45, 55, 72), 2)
            
            stats_text = (
                f"LANE QUEUES (PCU) ->  "
                f"North: {self.current_queues['A_north']} | "
                f"South: {self.current_queues['A_south']} | "
                f"East: {self.current_queues['A_east']} | "
                f"West: {self.current_queues['A_west']}   "
                f"[P] Pedestrian: {'ACTIVE' if self.pedestrian_trigger else 'OFF'}  "
                f"[E] Ambulance: {self.emergency_trigger or 'OFF'}"
            )
            cv2.putText(frame, stats_text, (20, h - 22), cv2.FONT_HERSHEY_DUPLEX, 0.52, (0, 255, 255), 1, cv2.LINE_AA)

            if self.show_display:
                cv2.imshow("Synapse City - Indian Traffic Vision Stream", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
                elif key == ord(' '):
                    self.paused = not self.paused
                elif key == ord('z'):
                    self.show_zones = not self.show_zones
                elif key == ord('p'):
                    self.pedestrian_trigger = 3 if self.pedestrian_trigger == 0 else 0
                    print(f"🚸 Pedestrian Crossing {'TRIGGERED' if self.pedestrian_trigger else 'CLEARED'}")
                elif key == ord('e'):
                    if self.emergency_trigger:
                        self.emergency_trigger = None
                        print("🚑 Emergency Cleared.")
                    else:
                        self.emergency_trigger = "A_north"
                        print("🚨 Ambulance Approaching on North!")

        self.running = False
        cap.release()
        cv2.destroyAllWindows()
        print("🛑 Vision Sensor stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="assets/indian_traffic.mp4", help="Video file path or stream URL")
    parser.add_argument("--api", default="http://127.0.0.1:8000/api/sensor/data", help="FastAPI backend URL")
    args = parser.parse_args()
    
    sensor = IndianTrafficVisionSensor(video_path=args.video, api_url=args.api)
    sensor.run()
