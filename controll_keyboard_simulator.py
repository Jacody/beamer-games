#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import cv2
import time
import mediapipe as mp
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt, pyqtSignal

# --- NEW: Import pynput for keyboard simulation ---
try:
    from pynput import keyboard
except ImportError:
    print("ERROR: pynput library not found.")
    print("Please install it using: pip install pynput")
    sys.exit(1)
# ---------------------------------------------------

# MediaPipe Module initialisieren
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# --- Hilfsfunktion zur Faust-Erkennung (unverändert) ---
def is_fist(hand_landmarks):
    """
    Überprüft, ob die gegebenen Hand-Landmarken eine Faust darstellen.
    """
    if not hand_landmarks:
        return False
    landmarks = hand_landmarks.landmark
    # Check if fingertips are below the PIP joint (Proximal Interphalangeal joint)
    # A lower y-coordinate means higher up in the image typically, so > checks if tip is lower than joint
    index_finger_closed = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y > landmarks[mp_hands.HandLandmark.INDEX_FINGER_PIP].y
    middle_finger_closed = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y > landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y
    ring_finger_closed = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP].y > landmarks[mp_hands.HandLandmark.RING_FINGER_PIP].y
    pinky_finger_closed = landmarks[mp_hands.HandLandmark.PINKY_TIP].y > landmarks[mp_hands.HandLandmark.PINKY_PIP].y
    # Optional: Check thumb (more robust fist detection)
    # thumb_closed = landmarks[mp_hands.HandLandmark.THUMB_TIP].x > landmarks[mp_hands.HandLandmark.THUMB_IP].x # Example logic
    return index_finger_closed and middle_finger_closed and ring_finger_closed and pinky_finger_closed

# --- Haupt-App-Klasse ---
class FistSideDetectorApp(QWidget):
    # Signals are kept but primarily used for logging/debugging now
    status_changed = pyqtSignal(int)
    fist_left_detected = pyqtSignal(bool)
    fist_right_detected = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fausterkennung + Tastatur Simulation (Links=A, Rechts=L)")
        self.setGeometry(100, 100, 800, 600) # Position and size of the camera window

        # --- NEW: Initialize Keyboard Controller ---
        self.keyboard_controller = keyboard.Controller()
        self.key_a_pressed = False # Track if 'a' is virtually pressed
        self.key_l_pressed = False # Track if 'l' is virtually pressed
        # -----------------------------------------

        self.cap = None
        self.kamera_index = -1
        self._initialize_camera() # Try to find and open the camera

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.hand_detection = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2, # Detect up to two hands
            min_detection_confidence=0.6, # Slightly higher confidence
            min_tracking_confidence=0.6
        )

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # Statusvariablen (mostly for internal logic now)
        self.last_fist_detected_time = 0
        self.debounce_time = 0.2 # Shorter debounce for responsiveness
        self.fist_currently_detected = False
        self.fist_on_left = False
        self.fist_on_right = False
        self.read_error_logged = False

        if self.cap and self.cap.isOpened():
            self.timer.start(30) # Update ~33 times per second
            print(f"✅ Timer gestartet. Verwende Kamera mit Index {self.kamera_index}.")
            print("--- Steuerung ---")
            print("Linke Faust im Bild: Simuliert 'a' Taste gedrückt")
            print("Rechte Faust im Bild: Simuliert 'l' Taste gedrückt")
            print("Keine Faust / Faust loslassen: Simuliert Tasten loslassen")
            print("-----------------")
        else:
            self.label.setText("⚠️ Keine funktionierende Kamera gefunden.")
            print("❌ Anwendung kann nicht starten, da keine Kamera verfügbar ist.")


    def _initialize_camera(self):
        """Initialisiert die Kamera (versucht zuerst die interne Kamera, dann die externe USB-Kamera)."""
        # Zuerst die interne Kamera versuchen (Index 0)
        self.kamera_index = 0
        print(f"🔄 Versuche interne Kamera (Index {self.kamera_index})...")
        
        # Versuche die interne Kamera mit verschiedenen Backends
        cap_internal = cv2.VideoCapture(self.kamera_index, cv2.CAP_DSHOW)  # DirectShow für Windows
        
        if self._is_camera_working(cap_internal, self.kamera_index):
            print(f"✅ Interne Kamera (Index {self.kamera_index}) OK.")
            self.cap = cap_internal
        else:
            print(f"⚠️ Interne Kamera (Index {self.kamera_index}) mit DirectShow nicht OK.")
            cap_internal.release()
            
            # Versuche noch einmal mit dem Standard-Backend
            print(f"🔄 Versuche interne Kamera (Index {self.kamera_index}) mit Standard-Backend...")
            cap_internal_std = cv2.VideoCapture(self.kamera_index)
            
            if self._is_camera_working(cap_internal_std, self.kamera_index):
                print(f"✅ Interne Kamera (Index {self.kamera_index}) mit Standard-Backend OK.")
                self.cap = cap_internal_std
            else:
                print(f"⚠️ Interne Kamera (Index {self.kamera_index}) nicht erreichbar.")
                cap_internal_std.release()
                
                # Jetzt die externe USB-Kamera versuchen (Index 1)
                self.kamera_index = 1
                print(f"🔄 Versuche externe USB-Kamera (Index {self.kamera_index})...")
                
                # Versuche die externe Kamera mit verschiedenen Backends
                cap_external = cv2.VideoCapture(self.kamera_index, cv2.CAP_DSHOW)
                
                if self._is_camera_working(cap_external, self.kamera_index):
                    print(f"✅ Externe USB-Kamera (Index {self.kamera_index}) OK.")
                    self.cap = cap_external
                else:
                    print(f"⚠️ Externe USB-Kamera (Index {self.kamera_index}) mit DirectShow nicht OK.")
                    cap_external.release()
                    
                    # Versuche noch einmal mit dem Standard-Backend
                    print(f"🔄 Versuche externe USB-Kamera (Index {self.kamera_index}) mit Standard-Backend...")
                    cap_external_std = cv2.VideoCapture(self.kamera_index)
                    
                    if self._is_camera_working(cap_external_std, self.kamera_index):
                        print(f"✅ Externe USB-Kamera (Index {self.kamera_index}) mit Standard-Backend OK.")
                        self.cap = cap_external_std
                    else:
                        print(f"❌ Keine funktionierende Kamera gefunden.")
                        cap_external_std.release()
                        self.cap = None
                        self.kamera_index = -1

        # Kamera-Einstellungen anwenden, wenn eine Kamera gefunden wurde
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"⚙️ Versuchte Auflösung 640x480, tatsächliche Auflösung: {int(actual_width)}x{int(actual_height)}")


    def _is_camera_working(self, capture_object, index):
        """Prüft Kamera."""
        if not capture_object or not capture_object.isOpened():
            print(f"   -> Fehler: Kamera {index} nicht geöffnet.")
            return False
        ret, frame = capture_object.read()
        if not ret or frame is None:
            print(f"   -> Fehler: Kein Frame von Kamera {index} lesbar.")
            return False
        print(f"   -> Erfolg: Frame von Kamera {index} gelesen.")
        return True

    def update_frame(self):
        """Liest Frame, erkennt Hände/Fäuste, simuliert Tasten."""
        if not self.cap or not self.cap.isOpened():
             if not self.read_error_logged:
                 print(f"❌ Fehler: Kamera {self.kamera_index} nicht verbunden.")
                 self.label.setText(f"⚠️ Kamera {self.kamera_index} nicht verbunden.")
                 self.read_error_logged = True
                 
                 # NEU: Initialisiere eine Zählvariable für Wiederholungsversuche
                 if not hasattr(self, 'retry_count'):
                     self.retry_count = 0
                 
                 self.retry_count += 1
                 
                 # Nach 5 Fehlversuchen versuche die Kamera neu zu initialisieren
                 if self.retry_count >= 5:
                     print(f"🔄 Versuche Kamera neu zu initialisieren...")
                     self.retry_count = 0
                     
                     # Versuche die aktuelle Kamera neu zu öffnen
                     if self.cap:
                         self.cap.release()
                     
                     # Falls wir die interne Kamera verwenden, versuche auch die externe
                     if self.kamera_index == 0:
                         alt_index = 1
                         print(f"🔄 Interne Kamera funktioniert nicht. Versuche externe USB-Kamera (Index {alt_index})...")
                     # Falls wir die externe Kamera verwenden, versuche auch die interne
                     else:
                         alt_index = 0
                         print(f"🔄 Externe USB-Kamera funktioniert nicht. Versuche interne Kamera (Index {alt_index})...")
                     
                     # Kamera-Initialisierung neu starten
                     self._initialize_camera()
             return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            if not self.read_error_logged:
                print(f"❌ Fehler beim Lesen des Frames von Kamera {self.kamera_index}.")
                self.label.setText(f"⚠️ Fehler beim Lesen von Kamera {self.kamera_index}.")
                self.read_error_logged = True
                
                # NEU: Initialisiere eine Zählvariable für Wiederholungsversuche
                if not hasattr(self, 'frame_retry_count'):
                    self.frame_retry_count = 0
                
                self.frame_retry_count += 1
                
                # Nach mehreren fehlgeschlagenen Frame-Leseversuchen, Kamera neu initialisieren
                if self.frame_retry_count >= 10:
                    print(f"🔄 Zu viele fehlgeschlagene Leseversuche. Initialisiere Kamera neu...")
                    self.frame_retry_count = 0
                    self._initialize_camera()
            return
        else:
             if self.read_error_logged: 
                 print(f"✅ Frames von Kamera {self.kamera_index} gelesen.")
                 # Zurücksetzen der Zähler bei erfolgreicher Frame-Erfassung
                 if hasattr(self, 'retry_count'):
                     self.retry_count = 0
                 if hasattr(self, 'frame_retry_count'):
                     self.frame_retry_count = 0
             self.read_error_logged = False

        h, w, _ = frame.shape
        center_x = w // 2
        frame = cv2.flip(frame, 1) # Spiegeln
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        results = self.hand_detection.process(frame_rgb)
        frame_rgb.flags.writeable = True
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        cv2.line(frame_bgr, (center_x, 0), (center_x, h), (255, 0, 0), 2)

        # Reset status for this frame
        fist_detected_left_in_frame = False
        fist_detected_right_in_frame = False

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())

                if is_fist(hand_landmarks):
                    wrist_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                    wrist_x_pixel = int(wrist_landmark.x * w)

                    if wrist_x_pixel < center_x:
                        fist_detected_left_in_frame = True
                        cv2.putText(frame_bgr, 'Faust LINKS (A)', (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
                    else:
                        fist_detected_right_in_frame = True
                        cv2.putText(frame_bgr, 'Faust RECHTS (L)', (center_x + 10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)

        # --- Keyboard Simulation Logic ---
        # Left Fist ('a' key)
        if fist_detected_left_in_frame and not self.key_a_pressed:
            try:
                self.keyboard_controller.press('a')
                self.key_a_pressed = True
                print("SIM: 'a' pressed")
                self.fist_left_detected.emit(True) # Emit signal (optional)
            except Exception as e:
                 print(f"Error pressing 'a': {e}")
        elif not fist_detected_left_in_frame and self.key_a_pressed:
            try:
                self.keyboard_controller.release('a')
                self.key_a_pressed = False
                print("SIM: 'a' released")
                self.fist_left_detected.emit(False) # Emit signal (optional)
            except Exception as e:
                 print(f"Error releasing 'a': {e}")

        # Right Fist ('l' key)
        if fist_detected_right_in_frame and not self.key_l_pressed:
            try:
                self.keyboard_controller.press('l')
                self.key_l_pressed = True
                print("SIM: 'l' pressed")
                self.fist_right_detected.emit(True) # Emit signal (optional)
            except Exception as e:
                 print(f"Error pressing 'l': {e}")
        elif not fist_detected_right_in_frame and self.key_l_pressed:
            try:
                self.keyboard_controller.release('l')
                self.key_l_pressed = False
                print("SIM: 'l' released")
                self.fist_right_detected.emit(False) # Emit signal (optional)
            except Exception as e:
                 print(f"Error releasing 'l': {e}")
        # ----------------------------------

        # Update overall status signal (less critical now, but kept)
        any_fist_in_frame = fist_detected_left_in_frame or fist_detected_right_in_frame
        now = time.time()
        if any_fist_in_frame:
            self.last_fist_detected_time = now
            if not self.fist_currently_detected:
                self.fist_currently_detected = True
                self.status_changed.emit(1)
        elif self.fist_currently_detected and (now - self.last_fist_detected_time > self.debounce_time):
             self.fist_currently_detected = False
             self.status_changed.emit(0)


        # Display the image
        rgb_image_for_display = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image_for_display.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image_for_display.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled_pixmap)


    def closeEvent(self, event):
        """Ressourcen freigeben, sicherstellen, dass Tasten losgelassen werden."""
        print("🔌 Anwendung wird beendet. Gebe Ressourcen frei...")
        self.timer.stop()
        if self.cap:
            self.cap.release()
        if hasattr(self, 'hand_detection'): # Check if initialized
            self.hand_detection.close()

        # --- NEW: Release keys on exit ---
        try:
            if self.key_a_pressed:
                print("Releasing 'a' on exit...")
                self.keyboard_controller.release('a')
            if self.key_l_pressed:
                print("Releasing 'l' on exit...")
                self.keyboard_controller.release('l')
        except Exception as e:
            print(f"Error releasing keys on exit: {e}")
        # ---------------------------------

        event.accept()

# Hauptteil
if __name__ == '__main__':
    app = QApplication(sys.argv)
    fist_app = FistSideDetectorApp()

    # Optional: Connect signals for debugging if needed
    # fist_app.status_changed.connect(lambda s: print(f"Debug Signal Overall: {s}"))
    # fist_app.fist_left_detected.connect(lambda d: print(f"Debug Signal Left: {d}"))
    # fist_app.fist_right_detected.connect(lambda d: print(f"Debug Signal Right: {d}"))

    fist_app.show()
    sys.exit(app.exec_())
