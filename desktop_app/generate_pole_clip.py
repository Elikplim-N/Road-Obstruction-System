"""
Generate a realistic Street Pole (Elevated / CCTV 45-degree angle) Road Video Clip
Simulates:
1. Camera mounted high on a street pole looking down at a 2-lane road.
2. Vehicles driving down Lane 1 and Lane 2 smoothly.
3. At t = 2.5s, a vehicle in Lane 1 experiences engine failure and comes to a complete halt.
4. Other traffic continues swerving or passing in Lane 2.
5. Stationed AI detects the stationary obstruction in Lane 1 and triggers the alarm.
"""

import cv2
import numpy as np
from pathlib import Path

def create_street_pole_clip(output_path, duration_seconds=12, fps=25):
    width, height = 800, 600
    total_frames = int(duration_seconds * fps)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    # Road coordinates from high pole view (curving from top-left to bottom-center)
    road_pts = np.array([
        (int(width * 0.15), 0),
        (int(width * 0.85), 0),
        (int(width * 0.95), height),
        (int(width * 0.05), height)
    ], dtype=np.int32)

    # Stalled car in Lane 1 (left lane)
    stalled_x = int(width * 0.35)
    stalled_y = 50
    stalled_target_y = int(height * 0.55)
    stalled_stopped = False

    for frame_idx in range(total_frames):
        t = frame_idx / fps
        img = np.zeros((height, width, 3), dtype=np.uint8)

        # Surrounding terrain / sidewalk (pole looking down)
        img[:, :] = [60, 95, 65]  # Greenish grass/roadside

        # Pavement / Asphalt
        cv2.fillPoly(img, [road_pts], (45, 45, 48))

        # Lane Boundaries (Solid white edges)
        cv2.line(img, (int(width * 0.15), 0), (int(width * 0.05), height), (240, 240, 240), 4)
        cv2.line(img, (int(width * 0.85), 0), (int(width * 0.95), height), (240, 240, 240), 4)

        # Center Lane Divider (Dashed yellow lines)
        mid_top = int(width * 0.50)
        mid_bot = int(width * 0.50)
        dash_offset = (frame_idx * 10) % 50
        for y_step in range(0, height, 40):
            cur_y = y_step + dash_offset
            if cur_y < height:
                cv2.line(img, (mid_top, cur_y), (mid_bot, min(height, cur_y + 20)), (0, 215, 255), 3)

        # Street pole shadow / pole corner indicator
        cv2.putText(img, "POLE-CAM #04 [NORTH CORRIDOR - ELEVATION: 6m]", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)

        # --- CAR 1: Stalled Car in Lane 1 ---
        if t < 2.5:
            stalled_y += (stalled_target_y - stalled_y) * 0.05
        else:
            stalled_stopped = True

        scale1 = 0.6 + (stalled_y / height) * 0.5
        cw1, ch1 = int(70 * scale1), int(110 * scale1)
        cx1, cy1 = stalled_x, int(stalled_y)

        # Shadow
        cv2.ellipse(img, (cx1, cy1), (cw1 // 2 + 5, ch1 // 2 + 5), 0, 0, 360, (20, 20, 20), -1)
        # Red vehicle chassis
        cv2.rectangle(img, (cx1 - cw1//2, cy1 - ch1//2), (cx1 + cw1//2, cy1 + ch1//2), (0, 0, 180), -1)
        # Windshields (front and rear)
        cv2.rectangle(img, (cx1 - cw1//2 + 5, cy1 - ch1//2 + 15), (cx1 + cw1//2 - 5, cy1 - ch1//2 + 35), (140, 160, 180), -1)
        cv2.rectangle(img, (cx1 - cw1//2 + 5, cy1 + ch1//2 - 35), (cx1 + cw1//2 - 5, cy1 + ch1//2 - 15), (140, 160, 180), -1)
        # Roof
        cv2.rectangle(img, (cx1 - cw1//2 + 8, cy1 - ch1//2 + 35), (cx1 + cw1//2 - 8, cy1 + ch1//2 - 35), (0, 0, 130), -1)

        # Hazard blinkers if stopped
        if stalled_stopped and (int(t * 3) % 2 == 0):
            cv2.circle(img, (cx1 - cw1//2 + 4, cy1 + ch1//2 - 6), 5, (0, 140, 255), -1)
            cv2.circle(img, (cx1 + cw1//2 - 4, cy1 + ch1//2 - 6), 5, (0, 140, 255), -1)

        # --- CAR 2: Moving Traffic in Lane 2 (smoothly passing) ---
        # Appears periodically every 4 seconds
        t_cycle = t % 3.5
        car2_y = int((t_cycle / 3.5) * (height + 150)) - 50
        if car2_y < height + 80:
            scale2 = 0.6 + (car2_y / height) * 0.5
            cw2, ch2 = int(70 * scale2), int(110 * scale2)
            cx2 = int(width * 0.70)
            cy2 = car2_y

            # Shadow & Blue sedan chassis
            cv2.ellipse(img, (cx2, cy2), (cw2 // 2 + 5, ch2 // 2 + 5), 0, 0, 360, (20, 20, 20), -1)
            cv2.rectangle(img, (cx2 - cw2//2, cy2 - ch2//2), (cx2 + cw2//2, cy2 + ch2//2), (180, 100, 0), -1)
            cv2.rectangle(img, (cx2 - cw2//2 + 6, cy2 - ch2//2 + 30), (cx2 + cw2//2 - 6, cy2 + ch2//2 - 30), (140, 70, 0), -1)

        # On-screen telemetry
        cv2.putText(img, f"POLE SENSOR TIME: {t:.1f}s", (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        if stalled_stopped:
            stop_duration = t - 2.5
            banner = f"HAZARD: VEHICLE STALLED IN LANE 1 ({stop_duration:.1f}s)"
            color = (0, 140, 255) if stop_duration < 2.5 else (0, 0, 255)
            cv2.putText(img, banner, (20, height - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        out.write(img)

    out.release()
    print(f"[Street Pole Generator] Saved clip to: {output_path}")

if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent / "sample_data" / "street_pole_demo.mp4"
    create_street_pole_clip(out_path)
