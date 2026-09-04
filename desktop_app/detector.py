"""
Road Object & Obstruction Detection Engine
Uses YOLOv8 to detect vehicles, pedestrians, debris, and tracks stationary obstructions
within an interactive road Region of Interest (ROI).
"""

import time
import cv2
import numpy as np
from collections import defaultdict
import config

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False


class TrackedObject:
    def __init__(self, track_id, class_name, bbox, timestamp):
        self.track_id = track_id
        self.class_name = class_name
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.stationary_start = timestamp
        self.is_stationary = False
        self.history = [(bbox, timestamp)]

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def bottom_center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)

    def update(self, bbox, timestamp):
        self.last_seen = timestamp
        prev_center = self.center
        self.bbox = bbox
        new_center = self.center

        # Check movement distance
        dx = new_center[0] - prev_center[0]
        dy = new_center[1] - prev_center[1]
        dist = np.sqrt(dx*dx + dy*dy)

        if dist < config.MOTION_PIXEL_THRESHOLD:
            # Not moving significantly
            if not self.is_stationary:
                self.stationary_start = timestamp
                self.is_stationary = True
        else:
            # Moving
            self.is_stationary = False
            self.stationary_start = timestamp

        self.history.append((bbox, timestamp))
        if len(self.history) > 30:
            self.history.pop(0)

    def stationary_duration(self, now):
        if not self.is_stationary:
            return 0.0
        return max(0.0, now - self.stationary_start)


class RoadObstructionDetector:
    def __init__(self, model_name=config.YOLO_MODEL_NAME, conf_thresh=config.CONFIDENCE_THRESHOLD):
        self.conf_thresh = conf_thresh
        self.model = None
        self.tracks = {}  # track_id -> TrackedObject
        self.next_track_id = 1
        self.roi_polygon = None  # in absolute pixel coordinates

        # Background Modeling & Calibration State
        self.bg_reference = None       # BGR reference frame of clean highway
        self.bg_gray = None            # Blurred grayscale reference
        self.bg_calibrated = False     # Whether reference is locked
        self.bg_calibration_time = None
        self.latest_clean_frame = None # Raw captured frame
        self.bg_threshold = 28         # Differential contrast threshold

        # Temporal Frame Differencing & Constant Change Tracking
        self.prev_gray = None
        self.latest_diff_pct = 0.0
        self.latest_constant_duration = 0.0
        self.latest_constant_triggered = False
        self.constant_change_threshold_s = getattr(config, 'STATIONARY_SECONDS_THRESHOLD', 2.5)
        self.diff_blobs = {}           # Persistent difference tracking blobs
        self.next_blob_id = 1

        if ULTRALYTICS_AVAILABLE:
            try:
                print(f"[AI] Loading YOLO model: {model_name}...")
                self.model = YOLO(model_name)
                print("[AI] YOLO model loaded successfully.")
            except Exception as e:
                print(f"[AI Warning] Failed to load YOLO: {e}. Running in computer vision fallback mode.")
        
        # OpenCV fallback detector (MOG2 background subtraction + contour analysis)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False)

    def set_roi(self, polygon_pts):
        """Sets the polygon zone (list of (x, y) tuples)."""
        self.roi_polygon = np.array(polygon_pts, dtype=np.int32)

    def is_point_in_roi(self, point):
        """Returns True if point (x, y) is inside the ROI polygon."""
        if self.roi_polygon is None:
            return True
        res = cv2.pointPolygonTest(self.roi_polygon, (float(point[0]), float(point[1])), False)
        return res >= 0

    def calibrate_background(self, frame=None):
        """
        Calibrates and locks the clean road background reference.
        Uses either the provided frame or the latest clean frame captured from camera.
        """
        target = frame if frame is not None else self.latest_clean_frame
        if target is None:
            return False, "No frame available to calibrate"

        self.bg_reference = target.copy()
        gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
        self.bg_gray = cv2.GaussianBlur(gray, (5, 5), 0)
        self.bg_calibrated = True
        self.bg_calibration_time = time.strftime("%Y-%m-%d %H:%M:%S")
        return True, f"Background calibrated successfully at {self.bg_calibration_time}"

    def reset_background(self):
        """Resets the background reference to uncalibrated state."""
        self.bg_reference = None
        self.bg_gray = None
        self.bg_calibrated = False
        self.bg_calibration_time = None
        self.latest_fg_mask = None
        self.latest_fg_vis = None
        self.prev_gray = None
        self.latest_diff_pct = 0.0
        self.latest_constant_duration = 0.0
        self.latest_constant_triggered = False
        self.diff_blobs.clear()
        return True, "Background reset"

    def get_differencing_telemetry(self):
        """Returns real-time telemetry on edge frame differencing and constant change state."""
        return {
            "diff_pct": round(self.latest_diff_pct, 1),
            "constant_duration": round(self.latest_constant_duration, 1),
            "threshold_seconds": self.constant_change_threshold_s,
            "constant_triggered": self.latest_constant_triggered,
            "state": "WARN_CONSTANT_OBSTRUCTION" if self.latest_constant_triggered else ("CHANGING" if self.latest_diff_pct > 2.0 else "CLEAR"),
            "mode": "Frame Differencing & Constant Change Thresholding"
        }

    def get_background_reference(self):
        """Returns the stored clean road background reference or latest frame."""
        if self.bg_reference is not None:
            return self.bg_reference
        if self.latest_clean_frame is not None:
            return self.latest_clean_frame
        # Default placeholder if no frame yet
        blank = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.putText(blank, "BACKGROUND NOT CALIBRATED", (180, 300),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (120, 120, 120), 2)
        return blank

    def get_foreground_visualization(self):
        """Returns visual representation of background subtraction mask."""
        if self.latest_fg_vis is not None:
            return self.latest_fg_vis
        blank = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.putText(blank, "AWAITING CALIBRATION / FRAME", (180, 300),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
        return blank

    def get_calibration_status(self):
        """Returns dictionary describing current background calibration status."""
        return {
            "calibrated": self.bg_calibrated,
            "calibrated_at": self.bg_calibration_time or "Not calibrated",
            "threshold": self.bg_threshold,
            "mode": "Static Road Reference Subtraction" if self.bg_calibrated else "Dynamic Adaptive MOG2"
        }

    def process_frame(self, frame, timestamp=None):
        """
        Processes a single video frame.
        timestamp: optional float timestamp (e.g. video position in seconds).
        Returns:
            annotated_frame: Frame with visual HUD and bounding boxes.
            alert_info: dict with status ('CLEAR', 'CAUTION', 'DANGER'), type, dist, duration, sound.
        """
        now = time.time() if timestamp is None else timestamp
        h, w = frame.shape[:2]

        # Store latest clean raw frame for snapshot & calibration
        self.latest_clean_frame = frame.copy()

        # Initialize default ROI if not set
        if self.roi_polygon is None:
            norm_pts = config.DEFAULT_ROI_NORMALIZED
            self.roi_polygon = np.array([[int(px * w), int(py * h)] for px, py in norm_pts], dtype=np.int32)

        # Auto-calibrate background from first frame if none locked yet
        if not self.bg_calibrated and self.bg_reference is None:
            self.calibrate_background(frame)

        # ROI Mask
        roi_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(roi_mask, [self.roi_polygon], 255)

        # Perform Differential Background Subtraction against Road Baseline
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray_frame, (5, 5), 0)

        if self.bg_gray is not None and self.bg_gray.shape == gray_blur.shape:
            diff = cv2.absdiff(self.bg_gray, gray_blur)
            _, thresh = cv2.threshold(diff, self.bg_threshold, 255, cv2.THRESH_BINARY)
            thresh_roi = cv2.bitwise_and(thresh, thresh, mask=roi_mask)

            # Morphological filtering to close gaps inside obstacle bodies and remove salt-and-pepper noise
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            thresh_roi = cv2.morphologyEx(thresh_roi, cv2.MORPH_CLOSE, kernel, iterations=2)
            thresh_roi = cv2.morphologyEx(thresh_roi, cv2.MORPH_OPEN, kernel, iterations=1)
            self.latest_fg_mask = thresh_roi

            # Measure variance / difference percentage in lane corridor
            roi_pixels = max(1, cv2.countNonZero(roi_mask))
            diff_pixels = cv2.countNonZero(thresh_roi)
            self.latest_diff_pct = (diff_pixels / roi_pixels) * 100.0

            # Generate visual overlay representation for operator dashboard
            vis = np.zeros((h, w, 3), dtype=np.uint8)
            vis[:, :] = [25, 25, 30] # Dark slate background
            # Draw ROI boundary in green
            cv2.polylines(vis, [self.roi_polygon], isClosed=True, color=(40, 180, 50), thickness=2)
            # Fill obstruction blobs in vivid coral/red
            vis[thresh_roi > 0] = [30, 60, 240]
            cv2.putText(vis, f"EDGE DIFF: {self.latest_diff_pct:.1f}% | THRESH: {self.constant_change_threshold_s}s", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            self.latest_fg_vis = vis
        else:
            thresh_roi = None
            self.latest_diff_pct = 0.0

        detections = []  # [(class_name, conf, [x1, y1, x2, y2])]

        if self.model is not None:
            results = self.model.track(frame, persist=True, verbose=False, conf=self.conf_thresh)
            if results and len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    if cls_id in config.TARGET_CLASSES:
                        class_name = config.TARGET_CLASSES[cls_id]
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        track_id = int(box.id[0].item()) if box.id is not None else None
                        detections.append((class_name, conf, [x1, y1, x2, y2], track_id))
        else:
            # High-speed Edge Detection: Combine Background Subtraction + HSV variance
            if thresh_roi is not None:
                contours, _ = cv2.findContours(thresh_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area > 1000:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        if bw > 30 and bh > 25:
                            aspect = bh / max(1, bw)
                            cls_name = "pedestrian" if (aspect > 1.5 and area < 4000) else "car"
                            detections.append((cls_name, 0.92, [x, y, x + bw, y + bh], None))

            # Fallback if no contours found via threshold
            if len(detections) == 0:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                sat_mask = cv2.inRange(hsv, (0, 35, 30), (180, 255, 255))
                obj_in_roi = cv2.bitwise_and(sat_mask, sat_mask, mask=roi_mask)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
                obj_in_roi = cv2.morphologyEx(obj_in_roi, cv2.MORPH_CLOSE, kernel)
                contours, _ = cv2.findContours(obj_in_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area > 1000:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        if bw > 30 and bh > 25:
                            aspect = bh / max(1, bw)
                            cls_name = "pedestrian" if (aspect > 1.5 and area < 4000) else "car"
                            detections.append((cls_name, 0.90, [x, y, x + bw, y + bh], None))

        # Hazard evaluation
        highest_status = "CLEAR"
        hazard_type = "NONE"
        hazard_dist = "SAFE"
        max_duration = 0.0
        sound_code = 0  # 0=mute, 1=caution, 2=danger

        active_track_ids = set()

        for class_name, conf, bbox, given_track_id in detections:
            x1, y1, x2, y2 = bbox
            bc_x = (x1 + x2) / 2.0
            bc_y = float(y2)

            in_danger_zone = self.is_point_in_roi((bc_x, bc_y))

            # Tracking logic
            track_id = given_track_id
            if track_id is None:
                # Match closest existing track or assign new
                track_id = self._match_or_create_track(class_name, bbox, now)

            active_track_ids.add(track_id)

            if track_id in self.tracks:
                self.tracks[track_id].update(bbox, now)
                tracked_obj = self.tracks[track_id]
            else:
                tracked_obj = TrackedObject(track_id, class_name, bbox, now)
                self.tracks[track_id] = tracked_obj

            stat_dur = tracked_obj.stationary_duration(now)

            # Determine proximity zone
            proximity = "FAR"
            if bc_y > h * config.ZONE_NEAR_Y_RATIO:
                proximity = "CLOSE"
            elif bc_y > h * (config.ZONE_NEAR_Y_RATIO * 0.75):
                proximity = "MEDIUM"

            # Obstruction Logic:
            # 1. Stationary Vehicle in Lane ROI
            is_vehicle = class_name in ["car", "truck", "bus", "motorcycle"]
            is_pedestrian = class_name in ["person", "dog", "horse"]

            box_color = (0, 255, 0) # Green normal
            status_text = ""

            if in_danger_zone:
                if is_pedestrian:
                    highest_status = "DANGER"
                    hazard_type = f"PEDESTRIAN"
                    hazard_dist = proximity
                    sound_code = 2
                    box_color = (0, 0, 255)
                    status_text = "! PEDESTRIAN IN LANE !"
                elif is_vehicle:
                    if stat_dur >= config.STATIONARY_SECONDS_THRESHOLD:
                        highest_status = "DANGER"
                        hazard_type = f"STALLED {class_name.upper()}"
                        hazard_dist = proximity
                        max_duration = max(max_duration, stat_dur)
                        sound_code = 2
                        box_color = (0, 0, 255) # Red
                        status_text = f"OBSTRUCTION! ({stat_dur:.1f}s)"
                    elif stat_dur > 0.8:
                        if highest_status != "DANGER":
                            highest_status = "CAUTION"
                            hazard_type = f"SLOW/STOPPING {class_name.upper()}"
                            hazard_dist = proximity
                            max_duration = max(max_duration, stat_dur)
                            sound_code = 1
                        box_color = (0, 165, 255) # Orange
                        status_text = f"STOPPED {stat_dur:.1f}s"
                    else:
                        box_color = (0, 255, 255) # Yellow moving in lane
                        status_text = f"{class_name} in lane"
            else:
                box_color = (180, 180, 180) # Gray outside lane
                status_text = f"{class_name} (shoulder)"

            # Draw Bounding Box
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            label = f"#{track_id} {class_name.upper()} {conf:.2f}"
            if status_text:
                label += f" | {status_text}"

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - 20)), (x1 + tw + 6, max(0, y1)), box_color, -1)
            cv2.putText(frame, label, (x1 + 3, max(12, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0) if box_color != (0, 0, 255) else (255, 255, 255), 1)

        # Cleanup old tracks
        stale_ids = [tid for tid, obj in self.tracks.items() if now - obj.last_seen > 3.0]
        for tid in stale_ids:
            del self.tracks[tid]

        # Draw ROI Polygon with alpha blend
        overlay = frame.copy()
        roi_color = (0, 255, 0)
        if highest_status == "DANGER":
            roi_color = (0, 0, 255)
        elif highest_status == "CAUTION":
            roi_color = (0, 165, 255)

        cv2.polylines(frame, [self.roi_polygon], isClosed=True, color=roi_color, thickness=3)
        cv2.fillPoly(overlay, [self.roi_polygon], roi_color)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

        # Draw HUD Alert Banner
        cv2.rectangle(frame, (0, 0), (w, 45), (20, 20, 20), -1)
        if highest_status == "DANGER":
            banner_bg = (0, 0, 200)
            banner_text = f" [!] ROAD OBSTRUCTION ALERT: {hazard_type} ({hazard_dist}) "
        elif highest_status == "CAUTION":
            banner_bg = (0, 140, 220)
            banner_text = f" [*] CAUTION: {hazard_type} IN LANE "
        else:
            banner_bg = (20, 140, 40)
            banner_text = " [OK] ROAD CLEAR - LANE SAFE "

        cv2.rectangle(frame, (10, 8), (w - 10, 38), banner_bg, -1)
        cv2.putText(frame, banner_text, (20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        self.latest_constant_duration = max_duration
        self.latest_constant_triggered = (highest_status == "DANGER")

        alert_info = {
            "status": highest_status,
            "type": hazard_type,
            "dist": hazard_dist,
            "duration": round(max_duration, 1),
            "sound": sound_code,
            "diff_pct": round(self.latest_diff_pct, 1),
            "constant_change": self.latest_constant_triggered,
            "constant_duration": round(max_duration, 1),
            "threshold_seconds": self.constant_change_threshold_s
        }

        return frame, alert_info

    def _match_or_create_track(self, class_name, bbox, now):
        """Simple centroid distance tracker when YOLO tracking id is not present."""
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        min_dist = float('inf')
        best_id = None

        for tid, tobj in self.tracks.items():
            if tobj.class_name == class_name:
                tcx, tcy = tobj.center
                d = np.sqrt((cx - tcx)**2 + (cy - tcy)**2)
                if d < 80 and d < min_dist:
                    min_dist = d
                    best_id = tid

        if best_id is not None:
            return best_id

        new_id = self.next_track_id
        self.next_track_id += 1
        return new_id
