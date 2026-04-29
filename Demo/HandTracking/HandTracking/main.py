import argparse
import os
import time

import cv2
import numpy as np
import pyarrow as pa
from dora import Node
import mediapipe as mp
from scipy.spatial.transform import Rotation

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands

# https://mediapipe.readthedocs.io/en/latest/solutions/hands.html


class CalibrationState:
    """Captures min/max of each finger tip vector during calibration,
    then normalizes output so the human hand's range maps to the
    Amazing Hand's full range."""

    def __init__(self, target_scale=1.3):
        self.active = False
        self.calibrated = False
        self.target_scale = target_scale
        # min/max per tip (4 fingers, 3 axes each)
        self.tips_min = [np.full(3, np.inf) for _ in range(4)]
        self.tips_max = [np.full(3, -np.inf) for _ in range(4)]
        self.sample_count = 0

    def start(self):
        self.active = True
        self.calibrated = False
        self.tips_min = [np.full(3, np.inf) for _ in range(4)]
        self.tips_max = [np.full(3, -np.inf) for _ in range(4)]
        self.sample_count = 0
        print("[Calibration] Started — open and close your hand 3 times, then press 'c' to finish")

    def update(self, tips):
        """Update min/max with current tip values. tips: list of 4 np.arrays (tip1..tip4)."""
        for i, tip in enumerate(tips):
            self.tips_min[i] = np.minimum(self.tips_min[i], tip)
            self.tips_max[i] = np.maximum(self.tips_max[i], tip)
        self.sample_count += 1

    def finish(self):
        self.active = False
        if self.sample_count < 10:
            print("[Calibration] Not enough samples, calibration discarded.")
            return
        self.calibrated = True
        for i in range(4):
            rng = self.tips_max[i] - self.tips_min[i]
            print(f"[Calibration] Finger {i+1}: min={self.tips_min[i]}, max={self.tips_max[i]}, range={rng}")
        print(f"[Calibration] Finished! target_scale={self.target_scale}  samples={self.sample_count}")

    def apply(self, tip, finger_idx):
        """Normalize tip using calibration data and scale to expanded target range."""
        if not self.calibrated:
            return tip
        raw_range = self.tips_max[finger_idx] - self.tips_min[finger_idx]
        # avoid division by zero on axes with no movement
        safe_range = np.where(np.abs(raw_range) < 1e-6, 1.0, raw_range)
        normalized = (tip - self.tips_min[finger_idx]) / safe_range  # [0, 1]
        normalized = np.clip(normalized, -0.1, 1.1)  # allow small overshoot
        # remap to expanded range
        target_range = raw_range * self.target_scale
        return self.tips_min[finger_idx] + normalized * target_range

    def draw_overlay(self, image):
        """Draw calibration status on the image."""
        h, w = image.shape[:2]
        if self.active:
            cv2.rectangle(image, (0, 0), (w, 40), (0, 0, 180), -1)
            cv2.putText(image, f"CALIBRATING  (samples: {self.sample_count})  |  Open/close hand 3x, then press 'c'",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        elif self.calibrated:
            cv2.rectangle(image, (0, 0), (w, 30), (0, 120, 0), -1)
            cv2.putText(image, f"CALIBRATED  (scale: {self.target_scale:.1f})  |  Press 'c' to re-calibrate",
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        else:
            cv2.putText(image, "Press 'c' to calibrate", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        return image


def process_img(hand_proc, image, calibration=None):
    image.flags.writeable = False
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hand_proc.process(image)
    # img_width,img_height,_ =image.shape
    # Draw the hand annotations on the image.
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    r_res=None
    l_res=None
    if results.multi_hand_landmarks:

      # print('Handedness:', results.multi_handedness)
      # print(results.multi_hand_world_landmarks)

      for index,handedness_classif in enumerate(results.multi_handedness):
          if handedness_classif.classification[0].score>0.8: #let's considere only one right hand


      # for hand_landmarks in results.multi_hand_landmarks:
      #     tip_x=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x-hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].x
      #     tip_y=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y-hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
      #     tip_z=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].z-hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].z
      #     print(f'TIP: {tip_x} {tip_y} {tip_z}')
      #     mp_drawing.draw_landmarks(
      #         image,
      #         hand_landmarks,
      #         mp_hands.HAND_CONNECTIONS,
      #         mp_drawing_styles.get_default_hand_landmarks_style(),
      #         mp_drawing_styles.get_default_hand_connections_style())


              hand_landmarks=results.multi_hand_world_landmarks[index] #metric
              # hand_landmarks=results.multi_hand_landmarks[index] #normalized
              hand_landmarks_norm=results.multi_hand_landmarks[index] #normalized





              tip1_x=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x-hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].x
              tip1_y=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y-hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
              tip1_z=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].z-hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].z

              tip2_x=hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].x-hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].x
              tip2_y=hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y-hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y
              tip2_z=hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].z-hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].z

              tip3_x=hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].x-hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP].x
              tip3_y=hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].y-hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP].y
              tip3_z=hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].z-hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP].z

              tip4_x=hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].x-hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_MCP].x
              tip4_y=hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].y-hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_MCP].y
              tip4_z=hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].z-hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_MCP].z


              # tip1_x=hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x-hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].x
              # tip1_y=hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y-hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
              # tip1_z=hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].z-hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].z

              # tip2_x=hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].x-hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].x
              # tip2_y=hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y-hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y
              # tip2_z=hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].z-hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].z

              # tip3_x=hand_landmarks_norm.landmark[mp_hands.HandLandmark.RING_FINGER_TIP].x-hand_landmarks_norm.landmark[mp_hands.HandLandmark.RING_FINGER_MCP].x
              # tip3_y=hand_landmarks_norm.landmark[mp_hands.HandLandmark.RING_FINGER_TIP].y-hand_landmarks_norm.landmark[mp_hands.HandLandmark.RING_FINGER_MCP].y
              # tip3_z=hand_landmarks_norm.landmark[mp_hands.HandLandmark.RING_FINGER_TIP].z-hand_landmarks_norm.landmark[mp_hands.HandLandmark.RING_FINGER_MCP].z

              # tip4_x=hand_landmarks_norm.landmark[mp_hands.HandLandmark.THUMB_TIP].x-hand_landmarks_norm.landmark[mp_hands.HandLandmark.THUMB_MCP].x
              # tip4_y=hand_landmarks_norm.landmark[mp_hands.HandLandmark.THUMB_TIP].y-hand_landmarks_norm.landmark[mp_hands.HandLandmark.THUMB_MCP].y
              # tip4_z=hand_landmarks_norm.landmark[mp_hands.HandLandmark.THUMB_TIP].z-hand_landmarks_norm.landmark[mp_hands.HandLandmark.THUMB_MCP].z





              # tip1_x=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x
              # tip1_y=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y
              # tip1_z=hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].z


              # print(f'TIP: {tip_x} {tip_y} {tip_z} ({hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x} {hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y} {hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].z})')
              mp_drawing.draw_landmarks(
                  image,
                  hand_landmarks_norm,
                  mp_hands.HAND_CONNECTIONS,
                  mp_drawing_styles.get_default_hand_landmarks_style(),
                  mp_drawing_styles.get_default_hand_connections_style())


              #define a new hand frame centered at marker WRIST (n°0) with z along the vector (WRIST,MIDDLE_FINGER_MCP) (0,9) and x is the "third dimension" normal to the plan of the palm (WRIST,MIDDLE_FINGER_MCP)x(WRIST,PINKY_MCP)
              # origin=np.array([hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].x,hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].y,hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].z])
              # mid_mcp=np.array([hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].x,hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y,hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].z])
              # unit_z=mid_mcp-origin
              # unit_z=unit_z/np.linalg.norm(unit_z)
              # pinky_mcp=np.array([hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP].x,hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP].y,hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP].z])

              #rotate everything in a hand referential
              origin=np.array([hand_landmarks_norm.landmark[mp_hands.HandLandmark.WRIST].x,hand_landmarks_norm.landmark[mp_hands.HandLandmark.WRIST].y,hand_landmarks_norm.landmark[mp_hands.HandLandmark.WRIST].z]) #wrist base as the origin
              mid_mcp=np.array([hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].x,hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y,hand_landmarks_norm.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].z]) #base of the middle finger
              unit_z=mid_mcp-origin #z is unit vector from base of wrist toward base of middle finger
              unit_z=unit_z/np.linalg.norm(unit_z)
              pinky_mcp=np.array([hand_landmarks_norm.landmark[mp_hands.HandLandmark.PINKY_MCP].x,hand_landmarks_norm.landmark[mp_hands.HandLandmark.PINKY_MCP].y,hand_landmarks_norm.landmark[mp_hands.HandLandmark.PINKY_MCP].z]) #base of the pinky finger

              index_mcp=np.array([hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].x,hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].y,hand_landmarks_norm.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].z]) #base of the index finger


              # print(f"ORIGIN: {origin} MID: {mid_mcp}")

              if handedness_classif.classification[0].label=='Right':
                  vec_towards_y=pinky_mcp-origin #vector from wrist base towards pinky base
              if handedness_classif.classification[0].label=='Left':
                  vec_towards_y=index_mcp-origin #vector from wrist base towards pinky base
              # unit_x=np.cross(unit_z,vec_towards_y)
              # vec_towards_y=pinky_mcp-origin #vector from wrist base towards pinky base

              unit_x=np.cross(vec_towards_y,unit_z) #we say unit x is the cross product of z and the vector towards pinky

              unit_x=unit_x/np.linalg.norm(unit_x)

              unit_y=np.cross(unit_z,unit_x)
              # unit_y=np.cross(unit_x,unit_z)





              if handedness_classif.classification[0].label=='Right':
              # A=np.array([unit_x,unit_y,unit_z]).reshape((3,3))
                  R=np.array([unit_x,-unit_y,unit_z]).reshape((3,3)) #-y because of mirror?
              if handedness_classif.classification[0].label=='Left':
                  R=np.array([unit_x,-unit_y,unit_z]).reshape((3,3)) #-y because of mirror?
              tip1=R@np.array([tip1_x,tip1_y,tip1_z])
              tip2=R@np.array([tip2_x,tip2_y,tip2_z])
              tip3=R@np.array([tip3_x,tip3_y,tip3_z])
              tip4=R@np.array([tip4_x,tip4_y,tip4_z])

              # --- Calibration: update or apply ---
              if calibration is not None:
                  if calibration.active:
                      calibration.update([tip1, tip2, tip3, tip4])
                  elif calibration.calibrated:
                      tip1 = calibration.apply(tip1, 0)
                      tip2 = calibration.apply(tip2, 1)
                      tip3 = calibration.apply(tip3, 2)
                      tip4 = calibration.apply(tip4, 3)

              # scale=0.01
              # image = cv2.drawFrameAxes(image, K, disto, rotV, origin, scale)

              # res=[{'r_tip1': [tip1_x,tip1_y,tip1_z],'r_tip2': [tip2_x,tip2_y,tip2_z],'r_tip3': [tip3_x,tip3_y,tip3_z],'r_tip4': [tip4_x,tip4_y,tip4_z]}]
              if handedness_classif.classification[0].label=='Right':
                  r_res=[{'r_tip1': tip1,'r_tip2': tip2,'r_tip3': tip3,'r_tip4': tip4}]
                  # print(f"RIGHT: {tip1_x:.3f} {tip1_y:.3f} {tip1_z:.3f} => {tip1}. {unit_x} {unit_y} {unit_z}")
              elif handedness_classif.classification[0].label=='Left':
                  l_res=[{'l_tip1': tip1,'l_tip2': tip2,'l_tip3': tip3,'l_tip4': tip4}]
                  # print(f"LEFT: {tip1_x:.3f} {tip1_y:.3f} {tip1_z:.3f} => {tip1}. {unit_x} {unit_y} {unit_z}")
    # Flip the image horizontally for a selfie-view display.
    return image,r_res,l_res
# cv2.imshow('MediaPipe Hands', cv2.flip(image, 1))


def main():

    node = Node()


    pa.array([])  # initialize pyarrow array
    cap = cv2.VideoCapture(1)

    calibration = CalibrationState(target_scale=1.3)

    with mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as hands:



        for event in node:

            event_type = event["type"]

            if event_type == "INPUT":
                event_id = event["id"]

                if event_id == "tick":
                    ret, frame = cap.read()

                    if not ret:
                        continue

                    frame = cv2.flip(frame, 1)
                    #process
                    frame,r_res,l_res=process_img(hands,frame,calibration)

                    if r_res is not None and not calibration.active:
                        node.send_output('r_hand_pos',pa.array(r_res))
                    if l_res is not None and not calibration.active:
                        node.send_output('l_hand_pos',pa.array(l_res))
                    # cv2.imshow('MediaPipe Hands', cv2.flip(frame, 1))
                    calibration.draw_overlay(frame)
                    cv2.imshow('MediaPipe Hands', frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    elif key == ord("c"):
                        if calibration.active:
                            calibration.finish()
                        else:
                            calibration.start()


            elif event_type == "ERROR":
                raise RuntimeError(event["error"])


if __name__ == "__main__":
    main()
