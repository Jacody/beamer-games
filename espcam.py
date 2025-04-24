import requests
import cv2
import numpy as np
import time
from PIL import Image
import io
import re # Für die Bereinigung des OCR-Ergebnisses
import sys # Für sys.exit()
import os # Für Pfadoperationen (Tesseract)

# --- Grundlegende Konfiguration ---
esp32_cam_ip = "192.168.178.178"  # IP-Adresse deiner ESP32-CAM
capture_url = f"http://{esp32_cam_ip}/capture"
connect_timeout = 10  # Sekunden für Verbindungsaufbau
read_timeout = 15     # Sekunden für Datenempfang

# --- ROI DEFINITION (Region of Interest) ---
# WICHTIG: Passe diese Werte EXAKT an deinen Zähler und dein Kamerabild an!
# Schau dir received_original.jpg an (ggf. mit SAVE_IMAGE_ONLY = True)
# und miss die Pixelkoordinaten im Bildbearbeitungsprogramm aus.
# Format: (Pixel von links, Pixel von oben, Breite des Bereichs, Höhe des Bereichs)
ROI_X = 5   # Pixel von links
ROI_Y = 65   # Pixel von oben
ROI_W = 35  # Breite des Bereichs
ROI_H = 55   # Höhe des Bereichs
roi_definition = (ROI_X, ROI_Y, ROI_W, ROI_H)

# --- Bildspeicher-Option ---
# Setze auf True, um nur das Originalbild von der Kamera zu holen, es als
# 'received_original.jpg' zu speichern und das Skript zu beenden.
# Nützlich, um die ROI-Werte oben korrekt einzustellen.
SAVE_IMAGE_ONLY = False

# --- OCR Engine Auswahl ---
# Wähle die zu verwendende OCR-Engine: 'tesseract' oder 'easyocr'
# 'tesseract': Kostenlos, lokal, oft gut nach Vorverarbeitung, Konfiguration wichtig.
# 'easyocr': Oft einfacher zu verwenden, gute Ergebnisse, benötigt separate Installation
#             (pip install easyocr torch torchvision torchaudio - oder mit tensorflow)
OCR_ENGINE = 'tesseract' # Wähle 'tesseract' oder 'easyocr'

# --- TESSERACT Konfiguration (Nur wenn OCR_ENGINE = 'tesseract') ---
TESSERACT_LANG = 'eng' # Sprache für Tesseract ('eng' oft gut für Zahlen, 'deu' auch möglich)
# Tesseract Page Segmentation Mode (PSM): Experimentiere hiermit!
# 6: Assume a single uniform block of text. (Oft gut)
# 7: Treat the image as a single text line. (Gut für Zähler)
# 8: Treat the image as a single word.
# 13: Raw line. Treat the image as a single text line, minimizing Tesseract-specific hacks.
TESSERACT_PSM = '7'
# Whitelist: Nur diese Zeichen soll Tesseract erkennen (sehr wichtig!)
# Füge ggf. ',' oder '.' hinzu, wenn dein Zähler Dezimalstellen hat.
TESSERACT_WHITELIST = '0123456789'
TESSERACT_CUSTOM_CONFIG = f'--oem 3 --psm {TESSERACT_PSM} -c tessedit_char_whitelist={TESSERACT_WHITELIST}'

# Versuche, Tesseract automatisch zu finden. Unter Windows musst du ggf. den Pfad manuell setzen.
try:
    import pytesseract
    # Beispiel für manuelle Pfadsetzung unter Windows (einkommentieren und anpassen):
    # if os.name == 'nt': # Nur für Windows
    #    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    tesseract_path = pytesseract.pytesseract.tesseract_cmd
    print(f"INFO: Tesseract gefunden unter: {tesseract_path}")
except ImportError:
    if OCR_ENGINE == 'tesseract':
        print("FEHLER: Pytesseract Modul nicht gefunden. Installiere es mit 'pip install pytesseract'.")
        sys.exit(1)
    else:
        print("INFO: Pytesseract nicht gefunden, wird aber nicht benötigt (OCR_ENGINE != 'tesseract').")
except Exception as e:
    if OCR_ENGINE == 'tesseract':
        print(f"WARNUNG: Konnte Tesseract nicht automatisch finden: {e}")
        print("Stelle sicher, dass Tesseract im System PATH ist oder setze 'pytesseract.pytesseract.tesseract_cmd' manuell im Code.")
        # Beispiel: pytesseract.pytesseract.tesseract_cmd = r'PFAD_ZU_DEINER_TESSERACT.EXE'


# --- EasyOCR Konfiguration (Nur wenn OCR_ENGINE = 'easyocr') ---
EASYOCR_LANG = ['en'] # Sprachen für EasyOCR (z.B. ['en'], ['de'], ['en', 'de'])
EASYOCR_READER = None # Wird später initialisiert, wenn benötigt

if OCR_ENGINE == 'easyocr':
    try:
        import easyocr
        print("INFO: Initialisiere EasyOCR Reader...")
        # Initialisiere den Reader einmal beim Start
        # gpu=True verwenden, wenn eine unterstützte GPU und CUDA/PyTorch vorhanden sind
        EASYOCR_READER = easyocr.Reader(EASYOCR_LANG, gpu=False)
        print("INFO: EasyOCR Reader erfolgreich initialisiert.")
    except ImportError:
        print("FEHLER: EasyOCR Modul nicht gefunden.")
        print("Installiere es mit 'pip install easyocr torch torchvision torchaudio' (für CPU/GPU)")
        print("oder 'pip install easyocr tensorflow' (für CPU/Tensorflow).")
        print("Setze OCR_ENGINE auf 'tesseract' oder installiere EasyOCR.")
        sys.exit(1)
    except Exception as e:
        print(f"FEHLER bei der Initialisierung von EasyOCR: {e}")
        sys.exit(1)


# --- Bildvorverarbeitungs-Optionen ---
# Experimentiere mit diesen Werten, um die Erkennung zu verbessern!
PREPROCESSING_SCALE_FACTOR = 2.0  # Um Faktor vergrößern (1.0 = keine Skalierung)
PREPROCESSING_USE_GRAYSCALE = True
# Thresholding Methode: 'adaptive' oder 'otsu' oder 'binary' oder None
PREPROCESSING_THRESHOLD_METHOD = 'adaptive'
PREPROCESSING_ADAPTIVE_BLOCK_SIZE = 15 # Ungerade Zahl > 1 (für adaptive)
PREPROCESSING_ADAPTIVE_C = 7         # Konstante (für adaptive)
PREPROCESSING_OTSU_THRESHOLD_VALUE = 0 # Wird von Otsu automatisch bestimmt
PREPROCESSING_BINARY_THRESHOLD_VALUE = 127 # Manueller Schwellwert (0-255)
PREPROCESSING_INVERT_THRESHOLD = True # Oft nötig, damit Ziffern weiß auf schwarzem Grund sind

# Rauschunterdrückung (vor oder nach Thresholding)
PREPROCESSING_USE_BLUR = True
PREPROCESSING_BLUR_METHOD = 'median' # 'median' oder 'gaussian'
PREPROCESSING_BLUR_KERNEL_SIZE = 3  # Ungerade Zahl (z.B. 3 oder 5)

# Morphologische Operationen (nach Thresholding)
PREPROCESSING_USE_MORPHOLOGY = False # True oder False
# 'open': Entfernt kleine Störungen (Erst Erosion, dann Dilatation)
# 'close': Schließt kleine Lücken (Erst Dilatation, dann Erosion)
PREPROCESSING_MORPH_OPERATION = 'close'
PREPROCESSING_MORPH_KERNEL_SIZE = (2, 2) # (Breite, Höhe) des Kernels


# --- Funktion zum Abrufen des Bildes ---
def get_image_from_esp32(url, conn_timeout, read_t):
    """Holt ein Einzelbild von der ESP32-CAM."""
    try:
        print(f"Versuche Bild von {url} abzurufen...")
        response = requests.get(url, timeout=(conn_timeout, read_t), stream=True) # stream=True kann helfen
        response.raise_for_status()
        if 'image/jpeg' in response.headers.get('Content-Type', ''):
            print("JPEG Bild erfolgreich empfangen.")
            # Lese die Bytes direkt
            image_bytes = response.content
            # Alternative, falls 'content' Probleme macht:
            # image_bytes = b''
            # for chunk in response.iter_content(chunk_size=8192):
            #     image_bytes += chunk
            if not image_bytes:
                print("FEHLER: Keine Bilddaten empfangen, obwohl Status OK war.")
                return None
            return image_bytes
        else:
            print(f"Unerwarteter Content-Type: {response.headers.get('Content-Type')}")
            # Lese einen Teil der Antwort für Debugging
            try:
                preview = response.text[:200]
                print(f"Antwort-Vorschau: {preview}...")
            except Exception:
                print("Antwort konnte nicht als Text gelesen werden.")
            return None
    except requests.exceptions.Timeout:
        print(f"Fehler: Timeout beim Zugriff auf {url} (Connect: {conn_timeout}s, Read: {read_t}s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen des Bildes: {e}")
        return None
    except Exception as e:
        print(f"Unerwarteter Fehler beim Bildabruf: {e}")
        return None

# --- Funktion zur Zählerstanderkennung ---
def recognize_meter_reading(image_bytes, roi_rect):
    """Erkennt den Zählerstand im definierten ROI eines Bildes."""
    if image_bytes is None:
        return None, None # Kein Bild, kein Ergebnis

    full_image_for_display = None # Zum Anzeigen am Ende

    try:
        # Bild mit OpenCV laden
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            print("Fehler: OpenCV konnte das Bild nicht dekodieren.")
            # Versuche PIL als Fallback
            try:
                pil_img = Image.open(io.BytesIO(image_bytes))
                img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                if img_bgr is None:
                     raise ValueError("Konvertierung von PIL zu OpenCV fehlgeschlagen")
                print("INFO: Bild erfolgreich mit PIL geladen und zu OpenCV konvertiert.")
            except Exception as pil_err:
                print(f"Fehler: Konnte Bild weder mit OpenCV noch mit PIL laden: {pil_err}")
                return None, None

        full_image_for_display = img_bgr.copy() # Kopie für die Anzeige mit ROI-Box
        print(f"Bildauflösung: {img_bgr.shape[1]}x{img_bgr.shape[0]}")

        # --- ROI Extraktion ---
        x, y, w, h = roi_rect
        img_height, img_width = img_bgr.shape[:2]

        # Überprüfe ROI Grenzen
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > img_width or y + h > img_height:
            print(f"FEHLER: ROI {roi_rect} ist ungültig oder liegt außerhalb der Bildgrenzen ({img_width}x{img_height})!")
            # Zeichne das ganze Bild als Fallback, damit man was sieht
            cv2.putText(full_image_for_display, "FEHLER: Ungueltiges ROI", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return None, full_image_for_display # Gib das Originalbild zurück

        roi = img_bgr[y:y+h, x:x+w]
        print(f"ROI extrahiert: Position ({x},{y}), Größe ({w}x{h})")

        # --- Vorverarbeitung des ROI für OCR ---
        processed_roi = roi.copy() # Arbeite auf einer Kopie des ROI

        # 1. Skalieren (optional, kann Erkennung verbessern)
        if PREPROCESSING_SCALE_FACTOR > 1.0:
            print(f"INFO: Skaliere ROI um Faktor {PREPROCESSING_SCALE_FACTOR}")
            new_w = int(w * PREPROCESSING_SCALE_FACTOR)
            new_h = int(h * PREPROCESSING_SCALE_FACTOR)
            processed_roi = cv2.resize(processed_roi, (new_w, new_h), interpolation=cv2.INTER_CUBIC) # INTER_CUBIC oder INTER_LINEAR testen

        # 2. Graustufenkonvertierung
        if PREPROCESSING_USE_GRAYSCALE:
            print("INFO: Konvertiere ROI zu Graustufen")
            processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2GRAY)
        else:
             # Falls keine Graustufen, braucht Tesseract BGR
             if OCR_ENGINE == 'tesseract' and len(processed_roi.shape) == 2:
                 processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_GRAY2BGR)


        # 3. Rauschunterdrückung (optional) - oft besser auf Graustufenbild
        if PREPROCESSING_USE_BLUR:
            if PREPROCESSING_BLUR_KERNEL_SIZE % 2 == 0 or PREPROCESSING_BLUR_KERNEL_SIZE < 1 :
                 print("WARNUNG: Blur Kernel Size muss ungerade und >= 1 sein. Setze auf 3.")
                 ksize = 3
            else:
                 ksize = PREPROCESSING_BLUR_KERNEL_SIZE

            if PREPROCESSING_BLUR_METHOD == 'median':
                print(f"INFO: Wende Median Blur an (Kernel: {ksize}x{ksize})")
                processed_roi = cv2.medianBlur(processed_roi, ksize)
            elif PREPROCESSING_BLUR_METHOD == 'gaussian':
                print(f"INFO: Wende Gaussian Blur an (Kernel: {ksize}x{ksize})")
                processed_roi = cv2.GaussianBlur(processed_roi, (ksize, ksize), 0)

        # 4. Thresholding (Schwarz/Weiß-Bild)
        threshold_applied = False
        if PREPROCESSING_THRESHOLD_METHOD == 'adaptive':
            print(f"INFO: Wende adaptives Thresholding an (Block: {PREPROCESSING_ADAPTIVE_BLOCK_SIZE}, C: {PREPROCESSING_ADAPTIVE_C}, Invertiert: {PREPROCESSING_INVERT_THRESHOLD})")
            thresh_type = cv2.THRESH_BINARY_INV if PREPROCESSING_INVERT_THRESHOLD else cv2.THRESH_BINARY
            if len(processed_roi.shape) == 3: # Falls noch BGR, erst Graustufen
                 gray_for_thresh = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2GRAY)
            else:
                 gray_for_thresh = processed_roi
            processed_roi = cv2.adaptiveThreshold(gray_for_thresh, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                  thresh_type, PREPROCESSING_ADAPTIVE_BLOCK_SIZE, PREPROCESSING_ADAPTIVE_C)
            threshold_applied = True
        elif PREPROCESSING_THRESHOLD_METHOD == 'otsu':
            print(f"INFO: Wende Otsu Thresholding an (Invertiert: {PREPROCESSING_INVERT_THRESHOLD})")
            thresh_type = cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU if PREPROCESSING_INVERT_THRESHOLD else cv2.THRESH_BINARY + cv2.THRESH_OTSU
            if len(processed_roi.shape) == 3: # Falls noch BGR, erst Graustufen
                 gray_for_thresh = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2GRAY)
            else:
                 gray_for_thresh = processed_roi
            ret, processed_roi = cv2.threshold(gray_for_thresh, PREPROCESSING_OTSU_THRESHOLD_VALUE, 255, thresh_type)
            print(f"INFO: Otsu Schwellwert gefunden: {ret}")
            threshold_applied = True
        elif PREPROCESSING_THRESHOLD_METHOD == 'binary':
             print(f"INFO: Wende binäres Thresholding an (Wert: {PREPROCESSING_BINARY_THRESHOLD_VALUE}, Invertiert: {PREPROCESSING_INVERT_THRESHOLD})")
             thresh_type = cv2.THRESH_BINARY_INV if PREPROCESSING_INVERT_THRESHOLD else cv2.THRESH_BINARY
             if len(processed_roi.shape) == 3: # Falls noch BGR, erst Graustufen
                 gray_for_thresh = cv2.cvtColor(processed_roi, cv2.COLOR_BGR2GRAY)
             else:
                 gray_for_thresh = processed_roi
             ret, processed_roi = cv2.threshold(gray_for_thresh, PREPROCESSING_BINARY_THRESHOLD_VALUE, 255, thresh_type)
             threshold_applied = True
        else:
            print("INFO: Kein Thresholding angewendet.")


        # 5. Morphologische Operationen (optional) - nur auf binärem Bild sinnvoll
        if PREPROCESSING_USE_MORPHOLOGY and threshold_applied:
            k_w, k_h = PREPROCESSING_MORPH_KERNEL_SIZE
            if k_w <=0 or k_h <=0:
                 print("WARNUNG: Morph Kernel Size ungültig. Setze auf (2,2).")
                 kernel = np.ones((2,2), np.uint8)
            else:
                 kernel = np.ones(PREPROCESSING_MORPH_KERNEL_SIZE, np.uint8)

            if PREPROCESSING_MORPH_OPERATION == 'open':
                print(f"INFO: Wende Morphological Opening an (Kernel: {PREPROCESSING_MORPH_KERNEL_SIZE})")
                processed_roi = cv2.morphologyEx(processed_roi, cv2.MORPH_OPEN, kernel)
            elif PREPROCESSING_MORPH_OPERATION == 'close':
                print(f"INFO: Wende Morphological Closing an (Kernel: {PREPROCESSING_MORPH_KERNEL_SIZE})")
                processed_roi = cv2.morphologyEx(processed_roi, cv2.MORPH_CLOSE, kernel)
        elif PREPROCESSING_USE_MORPHOLOGY and not threshold_applied:
             print("WARNUNG: Morphologie übersprungen, da kein Thresholding angewendet wurde.")


        # Speichere das endgültig bearbeitete ROI für Debugging
        try:
            cv2.imwrite("processed_roi.png", processed_roi)
            print("INFO: Bearbeitetes ROI gespeichert als processed_roi.png")
        except Exception as save_err:
            print(f"WARNUNG: Konnte processed_roi.png nicht speichern: {save_err}")

        # --- OCR Durchführung ---
        print(f"\n--- Starte OCR mit {OCR_ENGINE} ---")
        ocr_text_raw = ""
        cleaned_text = ""

        try:
            if OCR_ENGINE == 'tesseract':
                # Tesseract erwartet oft ein BGR Bild, auch wenn es intern Graustufen verwendet
                # Wenn unser processed_roi nur 1 Kanal hat (Grau/Binär), konvertiere es
                if len(processed_roi.shape) == 2:
                    ocr_input_image = cv2.cvtColor(processed_roi, cv2.COLOR_GRAY2BGR)
                else:
                    ocr_input_image = processed_roi

                ocr_text_raw = pytesseract.image_to_string(
                    ocr_input_image,
                    lang=TESSERACT_LANG,
                    config=TESSERACT_CUSTOM_CONFIG
                )

            elif OCR_ENGINE == 'easyocr':
                if EASYOCR_READER is None:
                    print("FEHLER: EasyOCR Reader ist nicht initialisiert.")
                    return None, full_image_for_display

                # EasyOCR erwartet ein BGR Bild (numpy array) oder einen Dateipfad
                # Es kann auch mit Graustufenbildern umgehen
                if len(processed_roi.shape) == 2:
                    ocr_input_image = cv2.cvtColor(processed_roi, cv2.COLOR_GRAY2BGR)
                else:
                    ocr_input_image = processed_roi

                # Führe Erkennung durch
                # allowlist: Nur Ziffern erlauben
                results = EASYOCR_READER.readtext(ocr_input_image, allowlist='0123456789', detail=0, paragraph=False)
                # detail=0 gibt nur den Text zurück, paragraph=False verhindert das Zusammenfassen von Zeilen
                ocr_text_raw = " ".join(results) # Füge erkannte Teile zusammen

            else:
                print(f"FEHLER: Unbekannte OCR_ENGINE '{OCR_ENGINE}'")
                return None, full_image_for_display

            # Bereinige das Ergebnis für beide Engines
            # Entferne alles, was keine Ziffer ist (inkl. Leerzeichen, Sonderzeichen)
            cleaned_text = re.sub(r'\D', '', ocr_text_raw)

            print(f"OCR Roh-Ergebnis: '{ocr_text_raw.strip()}'")
            print(f"OCR Bereinigtes Ergebnis (nur Ziffern): '{cleaned_text}'")

        except pytesseract.TesseractNotFoundError:
            print("FEHLER: Tesseract wurde nicht gefunden oder der Pfad ist falsch konfiguriert.")
            print("Bitte stelle sicher, dass Tesseract installiert ist und der Pfad in")
            print("pytesseract.pytesseract.tesseract_cmd korrekt gesetzt ist (besonders unter Windows).")
            return None, full_image_for_display # Gib Originalbild zurück
        except Exception as ocr_err:
            print(f"Fehler während der OCR mit {OCR_ENGINE}: {ocr_err}")
            # Versuche trotzdem, das Bild zurückzugeben
            # Zeichne ROI Rechteck in das Originalbild zur Visualisierung
            cv2.rectangle(full_image_for_display, (x, y), (x + w, y + h), (0, 0, 255), 2) # Rotes Rechteck bei Fehler
            cv2.putText(full_image_for_display, "OCR Error", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            return None, full_image_for_display


        # Zeichne das ROI Rechteck (grün bei Erfolg) in das Originalbild
        cv2.rectangle(full_image_for_display, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # Füge erkannten Text hinzu (optional)
        cv2.putText(full_image_for_display, f"Erkannt: {cleaned_text}", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return cleaned_text, full_image_for_display # Gib den erkannten Text und das Bild mit ROI zurück

    except cv2.error as cv_err:
         print(f"OpenCV Fehler bei der Bildverarbeitung: {cv_err}")
         # Versuche das Originalbild zurückzugeben, falls vorhanden
         if full_image_for_display is not None:
             # Zeichne Fehlermeldung ins Bild
             cv2.putText(full_image_for_display, "OpenCV Error", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
             return None, full_image_for_display
         else:
             return None, None # Kein Bild vorhanden
    except Exception as e:
        print(f"Allgemeiner Fehler bei der Bildverarbeitung: {e}")
        import traceback
        traceback.print_exc() # Zeige detaillierten Traceback
        # Versuche das Originalbild zurückzugeben, falls vorhanden
        if full_image_for_display is not None:
             cv2.putText(full_image_for_display, "Processing Error", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
             return None, full_image_for_display
        else:
            return None, None


# --- Hauptteil des Skripts ---
if __name__ == "__main__":
    print("--- Starte Zählerstand-Erkennung ---")
    print(f"Verbinde mit ESP32-CAM: {esp32_cam_ip}")
    print(f"Verwendete OCR Engine: {OCR_ENGINE}")
    if OCR_ENGINE == 'tesseract':
        print(f"Tesseract Config: Lang='{TESSERACT_LANG}', PSM='{TESSERACT_PSM}', Whitelist='{TESSERACT_WHITELIST}'")
    if OCR_ENGINE == 'easyocr':
        print(f"EasyOCR Config: Lang='{EASYOCR_LANG}'")


    image_data = get_image_from_esp32(capture_url, connect_timeout, read_timeout)

    if image_data:
        print(f"Bildgröße empfangen: {len(image_data)} Bytes")
        # Speichere das Originalbild immer (oder nur, wenn SAVE_IMAGE_ONLY)
        try:
            with open("received_original.jpg", "wb") as f:
                f.write(image_data)
            print("Originalbild gespeichert als received_original.jpg")

            # Lade das Bild direkt nach dem Speichern, um Auflösung zu prüfen (optional)
            temp_img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
            if temp_img is not None:
                h, w = temp_img.shape[:2]
                print(f"Bildauflösung: {w}x{h} Pixel")
                # Prüfe ob ROI Sinn macht
                if ROI_X + ROI_W > w or ROI_Y + ROI_H > h:
                     print("\nWARNUNG: Die definierten ROI-Koordinaten scheinen außerhalb")
                     print(f"         der Bildgrenzen ({w}x{h}) zu liegen. Bitte überprüfe")
                     print(f"         ROI_X={ROI_X}, ROI_Y={ROI_Y}, ROI_W={ROI_W}, ROI_H={ROI_H}")
                     print(f"         durch Betrachten von 'received_original.jpg'.\n")
                else:
                     print("INFO: ROI liegt innerhalb der Bildgrenzen.")

            # Wenn SAVE_IMAGE_ONLY aktiviert ist, beende das Programm hier
            if SAVE_IMAGE_ONLY:
                print("\n-> SAVE_IMAGE_ONLY ist True.")
                print("-> Bild wurde gespeichert. Bitte passe nun die ROI-Werte (ROI_X, ROI_Y, ROI_W, ROI_H)")
                print("-> oben in diesem Skript an, basierend auf 'received_original.jpg'.")
                print("-> Setze dann SAVE_IMAGE_ONLY = False, um die OCR-Erkennung zu starten.")
                sys.exit(0)

        except Exception as e:
            print(f"Fehler beim Speichern/Prüfen des Originalbilds: {e}")
            # Fahre trotzdem fort, wenn möglich

        # Führe die Erkennung durch
        print(f"\nVerwende ROI: x={ROI_X}, y={ROI_Y}, w={ROI_W}, h={ROI_H}")
        print("\n--- Starte Bildverarbeitung und OCR ---")
        recognized_text, processed_image_with_roi = recognize_meter_reading(image_data, roi_definition)

        print("\n--- Ergebnis ---")
        if recognized_text is not None and recognized_text != "":
            print(f"---> Erkannter Zählerstand: {recognized_text} <---")
        elif recognized_text is not None and recognized_text == "":
             print("---> OCR hat keinen Text/keine Ziffern im ROI gefunden. <---")
             print("     Mögliche Gründe: ROI falsch gesetzt, schlechte Bildqualität,")
             print("     ungünstige Vorverarbeitungsparameter, OCR-Engine unpassend.")
             print("     Überprüfe 'processed_roi.png' und 'received_original.jpg'.")
        else:
            print("---> Zählerstand konnte nicht erkannt werden (Fehler während der Verarbeitung). <---")
            print("     Überprüfe die Fehlermeldungen oben.")


        # Zeige das Bild mit dem markierten ROI an (falls vorhanden)
        if processed_image_with_roi is not None:
            print("\nZeige Bild mit markiertem ROI an...")
            # Skaliere das Bild ggf. herunter, wenn es zu groß für den Bildschirm ist
            max_display_width = 1200
            h, w = processed_image_with_roi.shape[:2]
            if w > max_display_width:
                scale = max_display_width / w
                display_img = cv2.resize(processed_image_with_roi, None, fx=scale, fy=scale)
            else:
                display_img = processed_image_with_roi

            cv2.imshow("Ergebnis mit ROI (Taste zum Schliessen druecken)", display_img)
            print("Drücke eine beliebige Taste im Bildfenster, um es zu schließen.")
            cv2.waitKey(0) # Warte unendlich auf Tastendruck
        else:
            print("Kein verarbeitetes Bild zum Anzeigen vorhanden.")

    else:
        print("\nFEHLER: Konnte kein Bild von der ESP32-CAM empfangen.")
        print("Überprüfe die IP-Adresse, Netzwerkverbindung und ob die ESP32-CAM läuft.")

    # Aufräumen
    print("\nSchließe OpenCV Fenster...")
    cv2.destroyAllWindows()
    print("Skript beendet.")