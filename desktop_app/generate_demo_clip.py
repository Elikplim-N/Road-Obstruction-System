"""
Generate a synthetic road obstruction test video (.mp4)
Simulates:
1. Driving down a highway/road.
2. An oncoming vehicle pulls into the lane and comes to an unexpected halt.
3. Car remains stationary in the lane for several seconds (simulating stalled vehicle obstruction).
4. System detects and triggers the alert.
"""

import cv2
import numpy as np
from pathlib import Path

def create_synthetic_road_clip(output_path, duration_seconds=12, fps=25):
    width, height = 800, 600
    total_frames = int(duration_seconds * fps)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    # Road vanishing point
    vp = (width // 2, int(height * 0.45))

    # Stalled car coordinates in simulation
    # Moves forward, then stops at frame 75 (3 sec in) through end
    car_x = width // 2
    car_y = vp[1] + 30
    target_y = int(height * 0.72)
    car_stopped = False

    for frame_idx in range(total_frames):
        t = frame_idx / fps
        img = np.zeros((height, width, 3), dtype=np.uint8)

        # Sky
        img[:vp[1], :] = [180, 140, 100]  # Light blue / dusk sky
        # Sun / Horizon glow
        cv2.circle(img, (vp[0] + 150, vp[1] - 40), 30, (220, 240, 255), -1)

        # Ground / Grass
        img[vp[1]:, :] = [45, 110, 50]

        # Road Polygon (Perspective)
        road_pts = np.array([
            (int(width * 0.05), height),
            (vp[0] - 25, vp[1]),
            (vp[0] + 25, vp[1]),
            (int(width * 0.95), height)
        ], dtype=np.int32)
        cv2.fillPoly(img, [road_pts], (50, 50, 50))  # Dark asphalt

        # Road boundaries (white lines)
        cv2.line(img, (int(width * 0.05), height), (vp[0] - 25, vp[1]), (255, 255, 255), 4)
        cv2.line(img, (int(width * 0.95), height), (vp[0] + 25, vp[1]), (255, 255, 255), 4)

        # Lane divider dashed lines (moving effect)
        dash_offset = (frame_idx * 12) % 60
        for y_step in range(vp[1] + 10, height, 40):
            cur_y = y_step + dash_offset
            if cur_y < height and cur_y > vp[1]:
                scale = (cur_y - vp[1]) / (height - vp[1])
                line_w = max(2, int(6 * scale))
                line_len = int(25 * scale)
                cv2.line(img, (vp[0], cur_y), (vp[0], min(height, cur_y + line_len)), (240, 240, 240), line_w)

        # Stationary Stalled Car Simulation
        # It moves forward down the lane until t = 3.0s, then stops permanently in lane!
        if t < 3.0:
            car_y += (target_y - car_y) * 0.04
        else:
            car_stopped = True

        scale_car = (car_y - vp[1]) / (height - vp[1])
        c_w = int(140 * scale_car)
        c_h = int(90 * scale_car)
        cx = int(car_x)
        cy = int(car_y)

        # Draw car body (Red Sedan)
        x1 = cx - c_w // 2
        y1 = cy - c_h
        x2 = cx + c_w // 2
        y2 = cy

        # Shadow
        cv2.ellipse(img, (cx, y2), (c_w // 2, int(10 * scale_car)), 0, 0, 360, (25, 25, 25), -1)
        # Main chassis
        cv2.rectangle(img, (x1, y1 + int(c_h * 0.35)), (x2, y2), (0, 0, 180), -1)
        # Roof / Cabin
        cabin_margin = int(c_w * 0.20)
        cv2.rectangle(img, (x1 + cabin_margin, y1), (x2 - cabin_margin, y1 + int(c_h * 0.45)), (0, 0, 140), -1)
        # Rear Windshield
        cv2.rectangle(img, (x1 + cabin_margin + 5, y1 + 5), (x2 - cabin_margin - 5, y1 + int(c_h * 0.40)), (180, 200, 220), -1)
        # Tail lights
        light_w = max(4, int(15 * scale_car))
        light_h = max(3, int(10 * scale_car))
        # Hazard lights blinking if stopped
        blink_on = (int(t * 4) % 2 == 0) if car_stopped else False
        tlight_color = (0, 140, 255) if blink_on else (0, 0, 255) # Orange blink or Red
        cv2.rectangle(img, (x1 + 6, y2 - light_h - 10), (x1 + 6 + light_w, y2 - 10), tlight_color, -1)
        cv2.rectangle(img, (x2 - 6 - light_w, y2 - light_h - 10), (x2 - 6, y2 - 10), tlight_color, -1)

        # License Plate
        cv2.rectangle(img, (cx - 20, y2 - 18), (cx + 20, y2 - 6), (255, 255, 255), -1)

        # Simulation timestamp & caption
        text = f"SIMULATION TIME: {t:.1f}s"
        cv2.putText(img, text, (20, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        if car_stopped:
            stopped_time = t - 3.0
            cv2.putText(img, f"[DEMO] VEHICLE STALLED IN LANE: {stopped_time:.1f}s", (20, height - 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255) if stopped_time < 2.5 else (0, 0, 255), 2)

        out.write(img)

    out.release()
    print(f"[Video Generator] Demo clip saved to: {output_path}")

if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent / "sample_data" / "road_obstruction_demo.mp4"
    create_synthetic_road_clip(out_file)
