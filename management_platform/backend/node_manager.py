"""
Highway Node & Asset Manager (Management Platform)
Tracks active Street Pole Sensing Units, Roadside Warning Signs (VMS),
and Patrol Vehicles deployed along the highway corridor.
"""

import time

class HighwayNodeManager:
    def __init__(self):
        self.nodes = {
            "POLE_04": {
                "id": "POLE_04",
                "name": "Street Pole #04 (Active AI Senser)",
                "location": "Corridor N-12 | Mile Marker 16.5 (Curve)",
                "elevation": "6.0m",
                "status": "ONLINE",
                "camera_fps": 25.0,
                "battery_v": 4.08,
                "battery_pct": 92,
                "solar_current_ma": 420,
                "wifi_rssi": -65,
                "lora_snr_db": 9.2,
                "is_sensing_source": True
            },
            "POLE_02": {
                "id": "POLE_02",
                "name": "Street Pole #02 (Bridge Ingress)",
                "location": "Corridor N-12 | Mile Marker 15.1",
                "elevation": "5.5m",
                "status": "ONLINE",
                "camera_fps": 20.0,
                "battery_v": 3.95,
                "battery_pct": 84,
                "solar_current_ma": 380,
                "wifi_rssi": -72,
                "lora_snr_db": 7.5,
                "is_sensing_source": False
            },
            "POLE_01": {
                "id": "POLE_01",
                "name": "Street Pole #01 (Toll Approach)",
                "location": "Corridor N-12 | Mile Marker 14.2",
                "elevation": "6.0m",
                "status": "ONLINE",
                "camera_fps": 22.0,
                "battery_v": 4.12,
                "battery_pct": 96,
                "solar_current_ma": 450,
                "wifi_rssi": -68,
                "lora_snr_db": 8.8,
                "is_sensing_source": False
            },
            "VMS_01": {
                "id": "VMS_01",
                "name": "Upstream Variable Message Sign #1",
                "location": "Corridor N-12 | Mile Marker 16.0 (500m Upstream)",
                "status": "ACTIVE",
                "display_text": "ROAD CLEAR - MAINTAIN SPEED",
                "lora_rssi": -76
            },
            "PATROL_09": {
                "id": "PATROL_09",
                "name": "Highway Safety Patrol Unit #09",
                "status": "PATROLLING",
                "distance_km": 1.4,
                "in_cabin_receiver_status": "MONITORING"
            }
        }

    def update_pole_telemetry(self, pole_id, hazard_active=False):
        if pole_id in self.nodes:
            node = self.nodes[pole_id]
            if hazard_active:
                node["status"] = "ALERT"
            else:
                node["status"] = "ONLINE"

    def set_vms_text(self, text):
        self.nodes["VMS_01"]["display_text"] = text

    def get_all_nodes(self):
        return list(self.nodes.values())
