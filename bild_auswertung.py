import cv2
import pytesseract
import re
import os # Modul zum Prüfen, ob die Datei existiert

# --- Konfiguration ---

# !!! WICHTIG: Passen Sie diesen Pfad ggf. an Ihren Tesseract-Installationsort an !!!
# Nur notwendig, wenn Tesseract nicht im System-PATH ist (häufig unter Windows)
# Beispiel für Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Beispiel für Linux/macOS (oft nicht nötig, wenn korrekt installiert):
# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract' # Pfad ggf. anpassen

# Pfad zu Ihrem Bild
# !!! ÄNDERN SIE DIES ZU IHREM BILDNAMEN/PFAD !!!
image_path = 'received_original.jpg' # Ersetzen Sie dies mit dem Pfad zu Ihrem Bild

# --- Vorbereitung ---
# Prüfen, ob das Bild existiert
if not os.path.exists(image_path):
    print(f"Fehler: Bilddatei nicht gefunden unter '{image_path}'")
    exit() # Beendet das Skript, wenn die Datei nicht existiert

# --- Bild laden ---
try:
    image = cv2.imread(image_path)
    if image is None:
        print(f"Fehler: Bild konnte nicht geladen werden. Prüfen Sie den Pfad und das Dateiformat: '{image_path}'")
        exit()
except Exception as e:
    print(f"Ein Fehler ist beim Laden des Bildes aufgetreten: {e}")
    exit()

# --- Bildvorverarbeitung (optional aber oft hilfreich) ---

# 1. Konvertierung in Graustufen (OCR arbeitet oft besser mit Graustufen)
gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# Bereich von Interesse (ROI) definieren wie in espcam.py angegeben
# Original-ROI
ROI_X = 5   # Pixel von links
ROI_Y = 65  # Pixel von oben
ROI_W = 35  # Breite des Bereichs
ROI_H = 55  # Höhe des Bereichs

# ROI in Originalbild einzeichnen
image_with_roi = image.copy()
# Rechteck zeichnen (Bild, Start-Punkt, End-Punkt, Farbe (BGR), Dicke)
cv2.rectangle(image_with_roi, (ROI_X, ROI_Y), (ROI_X + ROI_W, ROI_Y + ROI_H), (0, 255, 0), 2)
# Beschriftung hinzufügen
cv2.putText(image_with_roi, "ROI", (ROI_X, ROI_Y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
# Speichern des Bildes mit ROI-Rahmen
cv2.imwrite('image_with_roi.png', image_with_roi)

# Alternativ: Größere ROI auch einzeichnen
ROI_X_ALT = 0   # Pixel von links
ROI_Y_ALT = 60  # Pixel von oben
ROI_W_ALT = 50  # Breite des Bereichs
ROI_H_ALT = 70  # Höhe des Bereichs
# Alternative ROI in Bild einzeichnen (mit anderer Farbe)
cv2.rectangle(image_with_roi, (ROI_X_ALT, ROI_Y_ALT), (ROI_X_ALT + ROI_W_ALT, ROI_Y_ALT + ROI_H_ALT), (255, 0, 0), 2)
cv2.putText(image_with_roi, "Alt-ROI", (ROI_X_ALT, ROI_Y_ALT - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
# Speichern des Bildes mit beiden ROI-Rahmen
cv2.imwrite('image_with_both_roi.png', image_with_roi)

# ROI aus dem Bild extrahieren
roi_original = gray_image[ROI_Y:ROI_Y+ROI_H, ROI_X:ROI_X+ROI_W]
cv2.imwrite('roi_original.png', roi_original)

# Verarbeitung ohne Histogramm-Ausgleich probieren
# Adaptive Threshold anstatt globaler Threshold
roi_adapt = cv2.adaptiveThreshold(roi_original, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
cv2.imwrite('roi_adaptive_threshold.png', roi_adapt)

# Minimale Verarbeitung - sanftes Unschärfen und Threshold
roi_min = cv2.GaussianBlur(roi_original, (3, 3), 0)
_, roi_min_thresh = cv2.threshold(roi_min, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
cv2.imwrite('roi_minimal_processed.png', roi_min_thresh)

# Resizing für bessere OCR (Skalierung auf größeres Bild)
roi_resized = cv2.resize(roi_original, (roi_original.shape[1]*3, roi_original.shape[0]*3), interpolation=cv2.INTER_CUBIC)
_, roi_resized_thresh = cv2.threshold(roi_resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
cv2.imwrite('roi_resized.png', roi_resized_thresh)

# --- OCR mit Pytesseract ---
# Verschiedene Konfigurationen für Tesseract testen:

# Einzelner Charakter-Modus
config_single_char = r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
# Einzelne Textzeile
config_single_line = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
# Einzelnes Wort
config_single_word = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'

try:
    # OCR auf verschiedene verarbeitete ROIs anwenden
    text_original = pytesseract.image_to_string(roi_original, config=config_single_char)
    text_adapt = pytesseract.image_to_string(roi_adapt, config=config_single_char)
    text_min = pytesseract.image_to_string(roi_min_thresh, config=config_single_char)
    text_resized = pytesseract.image_to_string(roi_resized_thresh, config=config_single_char)
    
    # Alternative Konfigurationen testen
    text_original_line = pytesseract.image_to_string(roi_original, config=config_single_line)
    
    # Ergebnis mit der besten Erkennung verwenden
    results = {
        "Original ROI (Zeichen)": text_original.strip(),
        "Original ROI (Zeile)": text_original_line.strip(),
        "Adaptive Threshold": text_adapt.strip(),
        "Minimal verarbeitet": text_min.strip(),
        "Vergrößert": text_resized.strip()
    }
    
    # Alle Ergebnisse ausgeben
    print("\nOCR-Ergebnisse mit verschiedenen Methoden:")
    for method, result in results.items():
        print(f"{method}: '{result}'")
    
    # Das beste Ergebnis auswählen (hier vereinfacht - wir nehmen das erste nicht-leere Ergebnis)
    detected_text = next((result for result in results.values() if result), "")
    
    # Wenn alles leer ist, verwenden wir das Original-Ergebnis
    if not detected_text:
        detected_text = text_original
except pytesseract.TesseractNotFoundError:
    print("Fehler: Tesseract wurde nicht gefunden.")
    print("Stellen Sie sicher, dass Tesseract OCR installiert ist und der Pfad ggf.")
    print("in der Variable 'pytesseract.pytesseract.tesseract_cmd' oben im Skript korrekt gesetzt ist.")
    exit()
except Exception as e:
    print(f"Ein Fehler ist während der OCR-Verarbeitung aufgetreten: {e}")
    exit()

# --- Ergebnis bereinigen ---
# Entferne alle Zeichen, die keine Ziffern sind (Leerzeichen, Zeilenumbrüche etc.)
extracted_digits = re.sub(r'\D', '', detected_text)

# --- Ausgabe ---
print(f"Original erkannter Text: '{detected_text.strip()}'")
print(f"Extrahierte Ziffern (Zählerstand): '{extracted_digits}'")

# --- (Optional) Bilder anzeigen zur Fehlersuche ---
cv2.imshow("Originalbild", image)
cv2.imshow("Bild mit ROI", image_with_roi)
cv2.imshow("Original ROI", roi_original)
cv2.imshow("Adaptive Threshold", roi_adapt)
cv2.imshow("Minimal verarbeitet", roi_min_thresh)
cv2.imshow("Vergrößerte ROI", roi_resized_thresh)
cv2.waitKey(0) # Warte auf eine Taste
cv2.destroyAllWindows() # Schließe alle Fenster