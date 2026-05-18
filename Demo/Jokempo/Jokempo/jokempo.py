import time
import numpy as np
import random

import cv2
import pyarrow as pa
from dora import Node

from rustypot import Scs0009PyController

# Side
Side = 1  # 1=> Right Hand // 2=> Left Hand

# Speed
MaxSpeed = 6
CloseSpeed = 5

# Fingers middle poses
MiddlePos = [0, 0, 0, 0, 4, 0, -5, 1]  # replace values by your calibration results

# Gesture classification thresholds (per-finger)
# Calibrated 2026-05-17 from calibration_log.txt
#   Index:  closed ~0.040 (rock), open ~0.072 (paper)
#   Middle: closed ~0.043 (rock), open ~0.084 (paper)
#   Pinky:  closed ~0.042 (scissors), open ~0.065 (paper)
#   Thumb:  ~0.058-0.063 (not useful for classification)
INDEX_OPEN_THRESHOLD = 0.056
MIDDLE_OPEN_THRESHOLD = 0.063
RING_OPEN_THRESHOLD = 0.054  # pinky: scissors=0.042, paper=0.065

# Middle finger detection: middle is VERY extended (mean ~0.089)
MIDDLE_FINGER_THRESHOLD = 0.086

# Pointing gesture hold time for exit (4 seconds at ~20fps = 80 frames)
POINTING_STABLE_FRAMES = 80

# Game state
STATE_WAITING = 0       # Waiting for player to show open hand (ready)
STATE_COUNTDOWN = 1     # Countdown phase
STATE_RESULT = 2        # Show result
STATE_FORBIDDEN = 3     # Forbidden gesture detected - show reprimand
STATE_EXIT = 4          # Exiting

GESTURE_NONE = -1
GESTURE_ROCK = 0
GESTURE_PAPER = 1
GESTURE_SCISSORS = 2
GESTURE_POINTING = 3
GESTURE_MIDDLE_FINGER = 4

GESTURE_NAMES = {
    GESTURE_ROCK: "PEDRA",
    GESTURE_PAPER: "PAPEL",
    GESTURE_SCISSORS: "TESOURA",
    GESTURE_POINTING: "APONTAR",
    GESTURE_MIDDLE_FINGER: "!!!",
    GESTURE_NONE: "---",
}

# GUI colors
COLOR_BG = (40, 40, 40)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 200, 80)
COLOR_RED = (0, 0, 220)
COLOR_BLUE = (220, 140, 0)
COLOR_YELLOW = (0, 220, 220)
COLOR_GRAY = (150, 150, 150)

# GUI window size
GUI_WIDTH = 640
GUI_HEIGHT = 480


def classify_gesture(hand_pos):
    """Classify hand position into rock/paper/scissors/ok/middle_finger."""
    if hand_pos is None:
        return GESTURE_NONE

    tip1 = np.array(hand_pos['r_tip1'])  # index
    tip2 = np.array(hand_pos['r_tip2'])  # middle
    tip3 = np.array(hand_pos['r_tip3'])  # pinky

    mag1 = np.linalg.norm(tip1)
    mag2 = np.linalg.norm(tip2)
    mag3 = np.linalg.norm(tip3)

    index_open = mag1 > INDEX_OPEN_THRESHOLD
    middle_open = mag2 > MIDDLE_OPEN_THRESHOLD
    pinky_open = mag3 > RING_OPEN_THRESHOLD

    # Debug: print magnitudes for calibration
    print(f"[DEBUG] idx={mag1:.4f}({'O' if index_open else 'C'}) mid={mag2:.4f}({'O' if middle_open else 'C'}) pinky={mag3:.4f}({'O' if pinky_open else 'C'})")

    # Middle finger (forbidden): index closed, middle VERY open, pinky closed
    if not index_open and mag2 > MIDDLE_FINGER_THRESHOLD and not pinky_open:
        return GESTURE_MIDDLE_FINGER

    # Pointing gesture (exit): only index open, middle and pinky closed
    if index_open and not middle_open and not pinky_open:
        return GESTURE_POINTING

    # All fingers closed => Rock
    if not index_open and not middle_open and not pinky_open:
        return GESTURE_ROCK

    # All fingers open => Paper
    if index_open and middle_open and pinky_open:
        return GESTURE_PAPER

    # Index and middle open, pinky closed => Scissors
    if index_open and middle_open and not pinky_open:
        return GESTURE_SCISSORS

    return GESTURE_NONE


def judge(player_gesture, robot_gesture):
    """Returns: 0=draw, 1=player wins, 2=robot wins"""
    if player_gesture == robot_gesture:
        return 0
    if (player_gesture == GESTURE_ROCK and robot_gesture == GESTURE_SCISSORS) or \
       (player_gesture == GESTURE_PAPER and robot_gesture == GESTURE_ROCK) or \
       (player_gesture == GESTURE_SCISSORS and robot_gesture == GESTURE_PAPER):
        return 1
    return 2


def draw_gui(state, elapsed, detected_gesture, player_gesture, robot_gesture,
             result, score_player, score_robot, pointing_count):
    """Draw the game GUI overlay."""
    img = np.zeros((GUI_HEIGHT, GUI_WIDTH, 3), dtype=np.uint8)
    img[:] = COLOR_BG

    # Title
    cv2.putText(img, "JOKEMPO - Amazing Hand", (130, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, COLOR_WHITE, 2)

    # Score
    cv2.putText(img, f"Voce: {score_player}", (50, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_GREEN, 2)
    cv2.putText(img, f"Robo: {score_robot}", (450, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_RED, 2)

    # Divider
    cv2.line(img, (0, 105), (GUI_WIDTH, 105), COLOR_GRAY, 1)

    # Current detected gesture
    gesture_text = GESTURE_NAMES.get(detected_gesture, "---")
    cv2.putText(img, f"Detectado: {gesture_text}", (20, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_GRAY, 1)

    if state == STATE_WAITING:
        # Big instruction
        cv2.putText(img, "Mostre a mao aberta", (100, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_YELLOW, 2)
        cv2.putText(img, "para comecar!", (170, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_YELLOW, 2)

        # Pointing gesture hint to exit
        cv2.putText(img, "Aponte por 4s para sair", (160, 420),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_GRAY, 1)
        if pointing_count > 0:
            progress = min(pointing_count / POINTING_STABLE_FRAMES, 1.0)
            bar_w = int(300 * progress)
            cv2.rectangle(img, (170, 435), (170 + bar_w, 455), COLOR_GREEN, -1)
            cv2.rectangle(img, (170, 435), (470, 455), COLOR_GRAY, 1)
            cv2.putText(img, f"Saindo... {progress*100:.0f}%", (260, 475),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_GREEN, 1)

    elif state == STATE_COUNTDOWN:
        # Countdown display
        remaining = max(0, 3.0 - elapsed)
        countdown_num = int(remaining) + 1

        # Big number
        cv2.putText(img, str(countdown_num), (270, 300),
                    cv2.FONT_HERSHEY_SIMPLEX, 5.0, COLOR_YELLOW, 8)

        cv2.putText(img, "Faca seu gesto!", (190, 380),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, COLOR_WHITE, 2)

        # Progress bar
        progress = elapsed / 3.0
        bar_w = int(500 * progress)
        cv2.rectangle(img, (70, 400), (70 + bar_w, 420), COLOR_BLUE, -1)
        cv2.rectangle(img, (70, 400), (570, 420), COLOR_GRAY, 1)

    elif state == STATE_RESULT:
        # Show matchup
        p_name = GESTURE_NAMES.get(player_gesture, "---")
        r_name = GESTURE_NAMES.get(robot_gesture, "---")

        cv2.putText(img, "VOCE", (100, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_GREEN, 2)
        cv2.putText(img, p_name, (60, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOR_WHITE, 3)

        cv2.putText(img, "VS", (290, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_GRAY, 2)

        cv2.putText(img, "ROBO", (440, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_RED, 2)
        cv2.putText(img, r_name, (400, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOR_WHITE, 3)

        # Result
        if result == 0:
            result_text = "EMPATE!"
            result_color = COLOR_YELLOW
        elif result == 1:
            result_text = "VOCE GANHOU!"
            result_color = COLOR_GREEN
        else:
            result_text = "ROBO GANHOU!"
            result_color = COLOR_RED

        cv2.putText(img, result_text, (160, 340),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, result_color, 3)

        # Time remaining
        time_left = max(0, 2.0 - elapsed)
        cv2.putText(img, f"Proxima rodada em {time_left:.0f}s...", (190, 420),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_GRAY, 1)

    elif state == STATE_FORBIDDEN:
        # Red warning screen
        img[:] = (0, 0, 40)
        cv2.rectangle(img, (20, 20), (GUI_WIDTH - 20, GUI_HEIGHT - 20), COLOR_RED, 3)

        cv2.putText(img, "GESTO PROIBIDO!", (120, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, COLOR_RED, 3)

        cv2.putText(img, "Esse gesto nao e", (140, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_WHITE, 2)
        cv2.putText(img, "permitido neste jogo!", (110, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_WHITE, 2)

        cv2.putText(img, "Tenha mais respeito", (130, 350),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, COLOR_YELLOW, 2)
        cv2.putText(img, "com seu adversario!", (140, 400),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, COLOR_YELLOW, 2)

        time_left = max(0, 1.0 - elapsed)
        cv2.putText(img, f"Encerrando em {time_left:.0f}s...", (200, 460),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_GRAY, 1)

    cv2.imshow("Jokempo - Amazing Hand", img)
    key = cv2.waitKey(1) & 0xFF
    return key


c = Scs0009PyController(
    serial_port="COM8",
    baudrate=1000000,
    timeout=0.5,
)


def main():

    node = Node()

    time.sleep(0.5)  # let serial port settle after dora Node init
    c.write_torque_enable(1, 1)  # 1 = On / 2 = Off / 3 = Free

    state = STATE_WAITING
    state_start_time = time.time()
    player_gesture = GESTURE_NONE
    robot_gesture = GESTURE_NONE
    result = 0
    gesture_stable_count = 0
    pointing_count = 0
    STABLE_FRAMES = 10  # number of consistent frames to confirm gesture

    # Score
    score_player = 0
    score_robot = 0

    # Position GUI window next to camera window
    cv2.namedWindow("Jokempo - Amazing Hand", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("Jokempo - Amazing Hand", 660, 0)  # Right of camera (640px wide)

    OpenHand()
    print("[Jokempo] Waiting for player... Show open hand to start!")

    running = True
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

                detected = classify_gesture(hand_pos)
                elapsed = time.time() - state_start_time

                # Check for middle finger (forbidden) in any state except FORBIDDEN
                if state != STATE_FORBIDDEN and detected == GESTURE_MIDDLE_FINGER:
                    print("[Jokempo] FORBIDDEN GESTURE DETECTED!")
                    state = STATE_FORBIDDEN
                    state_start_time = time.time()
                    OpenHand()

                # Check for pointing to exit (only in WAITING state)
                elif state == STATE_WAITING:
                    if detected == GESTURE_POINTING:
                        pointing_count += 1
                        if pointing_count >= POINTING_STABLE_FRAMES:
                            print("[Jokempo] Pointing gesture held! Exiting...")
                            OpenHand()
                            state = STATE_EXIT
                            running = False
                    else:
                        pointing_count = 0

                    # Wait for player to show open hand (paper) as "ready" signal
                    if detected == GESTURE_PAPER:
                        gesture_stable_count += 1
                    else:
                        gesture_stable_count = 0

                    if gesture_stable_count >= STABLE_FRAMES:
                        print("[Jokempo] Player ready! Starting countdown...")
                        state = STATE_COUNTDOWN
                        state_start_time = time.time()
                        gesture_stable_count = 0
                        pointing_count = 0
                        OpenHand()

                elif state == STATE_COUNTDOWN:
                    # Give player 3 seconds to make their choice
                    if elapsed >= 3.0:
                        # Capture player's gesture
                        player_gesture = detected
                        if player_gesture in (GESTURE_NONE, GESTURE_POINTING, GESTURE_MIDDLE_FINGER):
                            print("[Jokempo] No valid gesture detected, try again!")
                            state = STATE_WAITING
                            state_start_time = time.time()
                            OpenHand()
                        else:
                            # Robot makes its random choice
                            robot_gesture = random.randint(0, 2)
                            print(f"[Jokempo] Player: {GESTURE_NAMES[player_gesture]} | Robot: {GESTURE_NAMES[robot_gesture]}")

                            # Execute robot pose
                            if robot_gesture == GESTURE_ROCK:
                                CloseHand()
                            elif robot_gesture == GESTURE_PAPER:
                                SpreadHand()
                            else:
                                Victory()

                            # Judge result
                            result = judge(player_gesture, robot_gesture)
                            result_str = ["EMPATE", "JOGADOR GANHOU", "ROBO GANHOU"][result]
                            print(f"[Jokempo] Result: {result_str}")

                            # Update score
                            if result == 1:
                                score_player += 1
                            elif result == 2:
                                score_robot += 1

                            node.send_output("jokempo_result", pa.array([{
                                "player": int(player_gesture),
                                "robot": int(robot_gesture),
                                "result": result,
                            }]))

                            state = STATE_RESULT
                            state_start_time = time.time()

                elif state == STATE_RESULT:
                    # Show result for 4 seconds then reset
                    if elapsed >= 4.0:
                        print("[Jokempo] New round! Show open hand to start.")
                        OpenHand()
                        state = STATE_WAITING
                        state_start_time = time.time()
                        gesture_stable_count = 0
                        pointing_count = 0

                elif state == STATE_FORBIDDEN:
                    # Show reprimand for 5 seconds then exit
                    if elapsed >= 5.0:
                        print("[Jokempo] Exiting due to forbidden gesture.")
                        OpenHand()
                        running = False

                # Draw GUI
                key = draw_gui(state, elapsed, detected, player_gesture,
                               robot_gesture, result, score_player, score_robot,
                               pointing_count)
                if key == ord('q') or key == 27:  # q or ESC
                    print("[Jokempo] Quit key pressed. Exiting...")
                    OpenHand()
                    running = False

            elif event_id == "tick":
                pass

        elif event_type == "ERROR":
            raise RuntimeError(event["error"])

    cv2.destroyAllWindows()
    node.send_output("stop", pa.array([True]))
    print(f"[Jokempo] Final Score - Voce: {score_player} | Robo: {score_robot}")


def OpenHand():
    Move_Index(-35, 35, MaxSpeed)
    Move_Middle(-35, 35, MaxSpeed)
    Move_Ring(-35, 35, MaxSpeed)
    Move_Thumb(-35, 35, MaxSpeed)


# Rock
def CloseHand():
    Move_Index(90, -90, CloseSpeed)
    Move_Middle(90, -90, CloseSpeed)
    Move_Ring(90, -90, CloseSpeed)
    Move_Thumb(90, -90, CloseSpeed + 1)


# Scissors
def Victory():
    if Side == 1:  # Right Hand
        Move_Index(-15, 65, MaxSpeed)
        Move_Middle(-65, 15, MaxSpeed)
        Move_Ring(90, -90, MaxSpeed)
        Move_Thumb(90, -90, MaxSpeed)

    if Side == 2:  # Left Hand
        Move_Index(-65, 15, MaxSpeed)
        Move_Middle(-15, 65, MaxSpeed)
        Move_Ring(90, -90, MaxSpeed)
        Move_Thumb(90, -90, MaxSpeed)


# Paper
def SpreadHand():
    if Side == 1:  # Right Hand
        Move_Index(4, 90, MaxSpeed)
        Move_Middle(-32, 32, MaxSpeed)
        Move_Ring(-90, -4, MaxSpeed)
        Move_Thumb(-90, -4, MaxSpeed)

    if Side == 2:  # Left Hand
        Move_Index(-60, 0, MaxSpeed)
        Move_Middle(-35, 35, MaxSpeed)
        Move_Ring(-4, 90, MaxSpeed)
        Move_Thumb(-4, 90, MaxSpeed)


def Move_Index(Angle_1, Angle_2, Speed):
    c.write_goal_speed(1, Speed)
    time.sleep(0.001)
    c.write_goal_speed(2, Speed)
    time.sleep(0.001)
    Pos_1 = np.deg2rad(MiddlePos[0] + Angle_1)
    Pos_2 = np.deg2rad(MiddlePos[1] + Angle_2)
    c.write_goal_position(1, Pos_1)
    c.write_goal_position(2, Pos_2)
    time.sleep(0.005)


def Move_Middle(Angle_1, Angle_2, Speed):
    c.write_goal_speed(3, Speed)
    time.sleep(0.001)
    c.write_goal_speed(4, Speed)
    time.sleep(0.001)
    Pos_1 = np.deg2rad(MiddlePos[2] + Angle_1)
    Pos_2 = np.deg2rad(MiddlePos[3] + Angle_2)
    c.write_goal_position(3, Pos_1)
    c.write_goal_position(4, Pos_2)
    time.sleep(0.005)


def Move_Ring(Angle_1, Angle_2, Speed):
    c.write_goal_speed(5, Speed)
    time.sleep(0.001)
    c.write_goal_speed(6, Speed)
    time.sleep(0.001)
    Pos_1 = np.deg2rad(MiddlePos[4] + Angle_1)
    Pos_2 = np.deg2rad(MiddlePos[5] + Angle_2)
    c.write_goal_position(5, Pos_1)
    c.write_goal_position(6, Pos_2)
    time.sleep(0.005)


def Move_Thumb(Angle_1, Angle_2, Speed):
    c.write_goal_speed(7, Speed)
    time.sleep(0.001)
    c.write_goal_speed(8, Speed)
    time.sleep(0.001)
    Pos_1 = np.deg2rad(MiddlePos[6] + Angle_1)
    Pos_2 = np.deg2rad(MiddlePos[7] + Angle_2)
    c.write_goal_position(7, Pos_1)
    c.write_goal_position(8, Pos_2)
    time.sleep(0.005)


def RandomPose():
    random_pose = random.randint(0, 2)
    if random_pose == 0:
        CloseHand()
    elif random_pose == 1:
        SpreadHand()
    else:
        Victory()


if __name__ == '__main__':
    main()



