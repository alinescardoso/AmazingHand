"""
Gesture Calibration Script for Jokempo
=======================================
Run via dora:  dora run Demo/dataflow_calibrate.yml
Or standalone:  python Demo/Jokempo/calibrate_gestures.py

Instructions:
  1. Press a key to select which gesture you'll show:
       R = Rock (pedra)
       P = Paper (papel)
       S = Scissors (tesoura)
       A = Pointing (apontar - only index up)
       M = Middle finger (dedo do meio)
       O = OK gesture
  2. Hold the gesture steady in front of the camera
  3. The script captures samples for ~3 seconds per gesture
  4. Press the same key again or wait for auto-stop
  5. Press Q to quit and save the calibration log

The log is saved to Demo/Jokempo/calibration_log.txt
"""

import time
import numpy as np
import cv2
import pyarrow as pa
from dora import Node

GESTURE_KEYS = {
    ord('r'): 'ROCK',
    ord('p'): 'PAPER',
    ord('s'): 'SCISSORS',
    ord('a'): 'POINTING',
    ord('m'): 'MIDDLE_FINGER',
    ord('o'): 'OK',
}

GUI_WIDTH = 500
GUI_HEIGHT = 400


def main():
    node = Node()

    # Storage: gesture_name -> list of (mag_idx, mag_mid, mag_pinky, mag_thumb)
    samples = {name: [] for name in GESTURE_KEYS.values()}

    current_gesture = None
    capture_start = None
    CAPTURE_DURATION = 3.0  # seconds per gesture

    cv2.namedWindow("Calibration", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("Calibration", 660, 0)

    print("=" * 60)
    print("  JOKEMPO GESTURE CALIBRATION")
    print("=" * 60)
    print("Keys: R=Rock  P=Paper  S=Scissors  A=Pointing  M=Middle  O=OK")
    print("Press the key, then show the gesture. Q to quit and save.")
    print("=" * 60)

    running = True
    last_mags = (0.0, 0.0, 0.0, 0.0)  # idx, mid, pinky, thumb

    for event in node:
        if not running:
            break

        event_type = event["type"]
        if event_type == "INPUT":
            event_id = event["id"]

            if event_id == "r_hand_pos":
                hand_data = event["value"].to_pylist()
                if not hand_data:
                    continue
                hand_pos = hand_data[0]

                tip1 = np.array(hand_pos['r_tip1'])  # index
                tip2 = np.array(hand_pos['r_tip2'])  # middle
                tip3 = np.array(hand_pos['r_tip3'])  # pinky
                tip4 = np.array(hand_pos['r_tip4'])  # thumb

                mag1 = np.linalg.norm(tip1)
                mag2 = np.linalg.norm(tip2)
                mag3 = np.linalg.norm(tip3)
                mag4 = np.linalg.norm(tip4)
                last_mags = (mag1, mag2, mag3, mag4)

                # If capturing, store sample
                if current_gesture is not None:
                    elapsed = time.time() - capture_start
                    if elapsed < CAPTURE_DURATION:
                        samples[current_gesture].append((mag1, mag2, mag3, mag4))
                    else:
                        n = len(samples[current_gesture])
                        print(f"  => {current_gesture}: captured {n} samples")
                        current_gesture = None

            # Draw GUI and handle keys on every event (tick or hand_pos)
            mag1, mag2, mag3, mag4 = last_mags

            # Auto-stop capture on timeout
            if current_gesture is not None and event_id != "r_hand_pos":
                elapsed = time.time() - capture_start
                if elapsed >= CAPTURE_DURATION:
                    n = len(samples[current_gesture])
                    print(f"  => {current_gesture}: captured {n} samples")
                    current_gesture = None

            img = np.zeros((GUI_HEIGHT, GUI_WIDTH, 3), dtype=np.uint8)
            img[:] = (40, 40, 40)

            cv2.putText(img, "CALIBRACAO DE GESTOS", (80, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

            # Current values
            y = 90
            cv2.putText(img, f"Index:  {mag1:.4f}", (30, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            cv2.putText(img, f"Middle: {mag2:.4f}", (30, y + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            cv2.putText(img, f"Pinky:  {mag3:.4f}", (30, y + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            cv2.putText(img, f"Thumb:  {mag4:.4f}", (30, y + 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            # Status
            if current_gesture is not None:
                elapsed = time.time() - capture_start
                remaining = max(0, CAPTURE_DURATION - elapsed)
                n = len(samples[current_gesture])
                cv2.putText(img, f"Capturando: {current_gesture}", (30, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 80), 2)
                cv2.putText(img, f"Amostras: {n}  |  Tempo: {remaining:.1f}s", (30, 275),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 80), 1)
                # Progress bar
                progress = min(elapsed / CAPTURE_DURATION, 1.0)
                bar_w = int(440 * progress)
                cv2.rectangle(img, (30, 290), (30 + bar_w, 310), (0, 200, 80), -1)
                cv2.rectangle(img, (30, 290), (470, 310), (150, 150, 150), 1)
            else:
                cv2.putText(img, "Pressione uma tecla para calibrar:", (30, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
                cv2.putText(img, "R=Pedra  P=Papel  S=Tesoura", (30, 270),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(img, "A=Apontar  M=DedoMedio  O=OK", (30, 300),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(img, "Q=Salvar e sair", (30, 330),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 255), 1)

            # Summary of captured gestures
            y_sum = 350
            summary = "  ".join(
                f"{name[:3]}:{len(s)}" for name, s in samples.items() if len(s) > 0
            )
            if summary:
                cv2.putText(img, summary, (30, y_sum),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            cv2.imshow("Calibration", img)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 27:
                running = False
            elif key in GESTURE_KEYS and current_gesture is None:
                current_gesture = GESTURE_KEYS[key]
                capture_start = time.time()
                samples[current_gesture] = []  # reset previous samples
                print(f"\n[Calibration] Starting capture for {current_gesture}...")
                print(f"  Show the gesture now! ({CAPTURE_DURATION}s)")

        elif event_type == "ERROR":
            raise RuntimeError(event["error"])

    cv2.destroyAllWindows()

    # Save calibration log
    log_path = "Jokempo/calibration_log.txt"
    with open(log_path, "w") as f:
        f.write("JOKEMPO GESTURE CALIBRATION LOG\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        for name, data in samples.items():
            if not data:
                f.write(f"{name}: NO SAMPLES\n\n")
                continue

            arr = np.array(data)
            idx_vals = arr[:, 0]
            mid_vals = arr[:, 1]
            pinky_vals = arr[:, 2]
            thumb_vals = arr[:, 3]

            f.write(f"{name} ({len(data)} samples)\n")
            f.write(f"  Index:  min={idx_vals.min():.5f}  max={idx_vals.max():.5f}  "
                    f"mean={idx_vals.mean():.5f}  std={idx_vals.std():.5f}\n")
            f.write(f"  Middle: min={mid_vals.min():.5f}  max={mid_vals.max():.5f}  "
                    f"mean={mid_vals.mean():.5f}  std={mid_vals.std():.5f}\n")
            f.write(f"  Pinky:  min={pinky_vals.min():.5f}  max={pinky_vals.max():.5f}  "
                    f"mean={pinky_vals.mean():.5f}  std={pinky_vals.std():.5f}\n")
            f.write(f"  Thumb:  min={thumb_vals.min():.5f}  max={thumb_vals.max():.5f}  "
                    f"mean={thumb_vals.mean():.5f}  std={thumb_vals.std():.5f}\n")
            f.write("\n")

        # Compute suggested thresholds
        f.write("=" * 70 + "\n")
        f.write("SUGGESTED THRESHOLDS\n")
        f.write("=" * 70 + "\n\n")

        def get_mean(gesture, col):
            if not samples[gesture]:
                return None
            return np.array(samples[gesture])[:, col].mean()

        # Index threshold: midpoint between rock(closed) and paper(open)
        rock_idx = get_mean('ROCK', 0)
        paper_idx = get_mean('PAPER', 0)
        if rock_idx is not None and paper_idx is not None:
            idx_thresh = (rock_idx + paper_idx) / 2
            f.write(f"INDEX_OPEN_THRESHOLD = {idx_thresh:.4f}  "
                    f"(rock={rock_idx:.4f}, paper={paper_idx:.4f})\n")

        # Middle threshold: midpoint between rock(closed) and paper(open)
        rock_mid = get_mean('ROCK', 1)
        paper_mid = get_mean('PAPER', 1)
        if rock_mid is not None and paper_mid is not None:
            mid_thresh = (rock_mid + paper_mid) / 2
            f.write(f"MIDDLE_OPEN_THRESHOLD = {mid_thresh:.4f}  "
                    f"(rock={rock_mid:.4f}, paper={paper_mid:.4f})\n")

        # Pinky threshold: midpoint between scissors(closed) and paper(open)
        scissors_pinky = get_mean('SCISSORS', 2)
        paper_pinky = get_mean('PAPER', 2)
        if scissors_pinky is not None and paper_pinky is not None:
            pinky_thresh = (scissors_pinky + paper_pinky) / 2
            f.write(f"RING_OPEN_THRESHOLD = {pinky_thresh:.4f}  "
                    f"(scissors={scissors_pinky:.4f}, paper={paper_pinky:.4f})\n")

        # Middle finger threshold
        mf_mid = get_mean('MIDDLE_FINGER', 1)
        if mf_mid is not None and paper_mid is not None:
            mf_thresh = (paper_mid + mf_mid) / 2
            f.write(f"MIDDLE_FINGER_THRESHOLD = {mf_thresh:.4f}  "
                    f"(paper_mid={paper_mid:.4f}, middle_finger_mid={mf_mid:.4f})\n")

        f.write("\n")

    print(f"\n[Calibration] Log saved to: {log_path}")

    # Print summary to console
    print("\n" + "=" * 60)
    print("CALIBRATION SUMMARY")
    print("=" * 60)
    for name, data in samples.items():
        if not data:
            continue
        arr = np.array(data)
        print(f"\n{name} ({len(data)} samples):")
        print(f"  Index:  mean={arr[:, 0].mean():.4f}")
        print(f"  Middle: mean={arr[:, 1].mean():.4f}")
        print(f"  Pinky:  mean={arr[:, 2].mean():.4f}")
        print(f"  Thumb:  mean={arr[:, 3].mean():.4f}")

    # Send stop signal
    node.send_output("stop", pa.array([True]))


if __name__ == '__main__':
    main()
