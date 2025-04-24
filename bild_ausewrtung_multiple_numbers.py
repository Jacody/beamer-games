import cv2
import pytesseract
import re
import os # Modul zum Prüfen, ob die Datei existiert
import numpy as np  # Für die Anzeige mehrerer Bilder

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

# --- Bildvorverarbeitung ---
# 1. Konvertierung in Graustufen (OCR arbeitet oft besser mit Graustufen)
gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# --- Definition der 6 ROIs ---
rois = [
    {"name": "ROI 1", "x": 5, "y": 65, "w": 35, "h": 55, "color": (0, 255, 0)},    # ROI 1 in Grün
    {"name": "ROI 2", "x": 60, "y": 65, "w": 35, "h": 55, "color": (255, 0, 0)},   # ROI 2 in Blau
    {"name": "ROI 3", "x": 120, "y": 65, "w": 35, "h": 55, "color": (0, 0, 255)},   # ROI 3 in Rot
    {"name": "ROI 4", "x": 160, "y": 65, "w": 35, "h": 55, "color": (255, 255, 0)},# ROI 4 in Cyan
    {"name": "ROI 5", "x": 225, "y": 65, "w": 35, "h": 55, "color": (255, 0, 255)},# ROI 5 in Magenta
    {"name": "ROI 6", "x": 280, "y": 65, "w": 35, "h": 55, "color": (0, 255, 255)} # ROI 6 in Gelb
]

# ROIs in Originalbild einzeichnen und extrahieren
image_with_rois = image.copy()
roi_images = []
roi_processed_images = []

for roi in rois:
    # ROI einzeichnen
    cv2.rectangle(image_with_rois, 
                 (roi["x"], roi["y"]), 
                 (roi["x"] + roi["w"], roi["y"] + roi["h"]), 
                 roi["color"], 2)
    cv2.putText(image_with_rois, roi["name"], 
                (roi["x"], roi["y"] - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, roi["color"], 2)
    
    # Prüfen, ob die ROI innerhalb des Bildes liegt
    if (roi["x"] >= 0 and roi["y"] >= 0 and 
        roi["x"] + roi["w"] <= image.shape[1] and 
        roi["y"] + roi["h"] <= image.shape[0]):
        
        # ROI extrahieren
        roi_img = gray_image[roi["y"]:roi["y"]+roi["h"], roi["x"]:roi["x"]+roi["w"]]
        
        # Prüfen, ob ROI nicht leer ist
        if roi_img.size > 0:
            roi_images.append(roi_img)
            
            # ROI verarbeiten
            # 1. Adaptive Threshold
            roi_adapt = cv2.adaptiveThreshold(roi_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                            cv2.THRESH_BINARY_INV, 11, 2)
            
            # 2. Minimale Verarbeitung mit Otsu-Thresholding
            roi_min = cv2.GaussianBlur(roi_img, (3, 3), 0)
            _, roi_min_thresh = cv2.threshold(roi_min, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 3. Vergrößerte Version für bessere OCR
            roi_resized = cv2.resize(roi_img, (roi_img.shape[1]*3, roi_img.shape[0]*3), 
                                    interpolation=cv2.INTER_CUBIC)
            _, roi_resized_thresh = cv2.threshold(roi_resized, 0, 255, 
                                                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Speichern der verarbeiteten ROIs
            roi_processed = {
                "original": roi_img,
                "adaptive": roi_adapt,
                "minimal": roi_min_thresh,
                "resized": roi_resized_thresh
            }
            roi_processed_images.append(roi_processed)
            
            # Optional: Speichern der ROIs als separate Bilder
            cv2.imwrite(f'{roi["name"].replace(" ", "_")}_original.png', roi_img)
            cv2.imwrite(f'{roi["name"].replace(" ", "_")}_adaptive.png', roi_adapt)
            cv2.imwrite(f'{roi["name"].replace(" ", "_")}_minimal.png', roi_min_thresh)
            cv2.imwrite(f'{roi["name"].replace(" ", "_")}_resized.png', roi_resized_thresh)
        else:
            print(f"Warnung: ROI {roi['name']} ist leer oder außerhalb des Bildes.")
    else:
        print(f"Warnung: ROI {roi['name']} liegt außerhalb des Bildes und wird übersprungen.")

# Speichern des Bildes mit allen ROIs
cv2.imwrite('image_with_all_rois.png', image_with_rois)

# --- OCR mit Pytesseract ---
# Verschiedene Konfigurationen für Tesseract testen:
# Wir verwenden jetzt den Page Segmentation Mode (PSM) und Output Engine Mode (OEM) mit Konfidenzwerten
config_single_char = r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
config_single_line = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
config_single_word = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'

# Sammeln aller Erkennungsergebnisse
all_recognition_results = []

try:
    for i, roi in enumerate(rois):
        if i >= len(roi_processed_images):
            print(f"Überspringe ROI {roi['name']}, da sie nicht erfolgreich verarbeitet wurde.")
            continue
            
        roi_processed = roi_processed_images[i]
        
        # OCR mit Konfidenzwerten für jede Erkennungsmethode
        # Basismethode: image_to_data gibt detaillierte Daten mit Konfidenzwerten zurück
        
        # 1. Original-ROI OCR mit Konfidenz (Einzelzeichenmodus)
        data_original = pytesseract.image_to_data(roi_processed["original"], config=config_single_char, 
                                                  output_type=pytesseract.Output.DICT)
        
        # 2. Original-ROI mit Zeilenerkennung
        data_original_line = pytesseract.image_to_data(roi_processed["original"], config=config_single_line, 
                                                      output_type=pytesseract.Output.DICT)
        
        # 3. Adaptive Threshold mit Einzelzeichenmodus
        data_adapt = pytesseract.image_to_data(roi_processed["adaptive"], config=config_single_char, 
                                              output_type=pytesseract.Output.DICT)
        
        # 4. Minimal verarbeitet mit Einzelzeichenmodus
        data_min = pytesseract.image_to_data(roi_processed["minimal"], config=config_single_char, 
                                            output_type=pytesseract.Output.DICT)
        
        # 5. Vergrößerte Version mit Einzelzeichenmodus
        data_resized = pytesseract.image_to_data(roi_processed["resized"], config=config_single_char, 
                                                output_type=pytesseract.Output.DICT)
        
        # Hilfsfunktion, um Text und durchschnittliche Konfidenz aus den OCR-Daten zu extrahieren
        def extract_text_and_confidence(data):
            texts = []
            confs = []
            
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:  # Nur gültige Konfidenzwerte (> 0)
                    texts.append(data['text'][i])
                    confs.append(float(data['conf'][i]))
            
            if texts:
                text = ' '.join(texts).strip()
                avg_conf = sum(confs) / len(confs) if confs else 0
                return text, avg_conf
            else:
                return "", 0.0
        
        # Ergebnisse mit Konfidenzwerten extrahieren
        text_original, conf_original = extract_text_and_confidence(data_original)
        text_original_line, conf_original_line = extract_text_and_confidence(data_original_line)
        text_adapt, conf_adapt = extract_text_and_confidence(data_adapt)
        text_min, conf_min = extract_text_and_confidence(data_min)
        text_resized, conf_resized = extract_text_and_confidence(data_resized)
        
        # Ergebnis mit der besten Erkennung verwenden
        results = {
            "Original (Zeichen)": {"text": text_original.strip(), "conf": conf_original},
            "Original (Zeile)": {"text": text_original_line.strip(), "conf": conf_original_line},
            "Adaptive Threshold": {"text": text_adapt.strip(), "conf": conf_adapt},
            "Minimal verarbeitet": {"text": text_min.strip(), "conf": conf_min},
            "Vergrößert": {"text": text_resized.strip(), "conf": conf_resized}
        }
        
        # Beste Methode auswählen - bevorzuge Methoden mit höherer Konfidenz
        best_method = None
        best_conf = -1
        best_text = ""
        
        for method, result in results.items():
            if result["text"] and result["conf"] > best_conf:
                best_conf = result["conf"]
                best_text = result["text"]
                best_method = method
        
        # Wenn keine Methode erfolgreich war, Standard-Fallback
        if not best_text:
            best_text = text_original
            best_method = "Original (Zeichen)"
            best_conf = conf_original
            
        # Bereinigen - nur Ziffern behalten
        extracted_digits = re.sub(r'\D', '', best_text)
        
        # Ergebnisse speichern
        all_recognition_results.append({
            "roi_name": roi["name"],
            "results": results,
            "best_method": best_method,
            "best_confidence": best_conf,
            "detected_text": best_text,
            "extracted_digits": extracted_digits
        })
        
except pytesseract.TesseractNotFoundError:
    print("Fehler: Tesseract wurde nicht gefunden.")
    print("Stellen Sie sicher, dass Tesseract OCR installiert ist und der Pfad ggf.")
    print("in der Variable 'pytesseract.pytesseract.tesseract_cmd' oben im Skript korrekt gesetzt ist.")
    exit()
except Exception as e:
    print(f"Ein Fehler ist während der OCR-Verarbeitung aufgetreten: {e}")
    exit()

# --- Ergebnisse ausgeben ---
print("\n--- OCR-Erkennungsergebnisse für alle ROIs ---")
for result in all_recognition_results:
    print(f"\n{result['roi_name']}:")
    print(f"  Erkannter Text: '{result['detected_text']}'")
    print(f"  Extrahierte Ziffern: '{result['extracted_digits']}'")
    print(f"  Beste Methode: {result['best_method']}")
    print(f"  Konfidenz: {result['best_confidence']:.2f}%")
    
    print("  Detaillierte Ergebnisse je Methode:")
    for method, res in result["results"].items():
        print(f"    - {method}: '{res['text']}' (Konfidenz: {res['conf']:.2f}%)")

# --- Optional: Zusammenfassung aller erkannten Zahlen mit Konfidenz ---
all_digits = [(result["extracted_digits"], result["best_confidence"]) for result in all_recognition_results]
print("\n--- Zusammenfassung aller erkannten Ziffern mit Konfidenz ---")
for i, (digits, conf) in enumerate(all_digits):
    if i < len(all_recognition_results):
        print(f"{all_recognition_results[i]['roi_name']}: {digits} (Konfidenz: {conf:.2f}%)")

# --- Bilder anzeigen ---
# Zeige das Originalbild mit allen ROIs
cv2.imshow("Originalbild mit allen ROIs", image_with_rois)

# Erstelle ein Gitter zum Anzeigen aller ROI-Bilder
if roi_images:  # Nur fortfahren, wenn wir ROIs haben
    # ROIs in einer Reihe anzeigen
    roi_display_images = []
    for i, roi_processed in enumerate(roi_processed_images):
        # Originales ROI anzeigen
        img = roi_processed["original"]
        h, w = img.shape
        # Text hinzufügen mit erkannten Ziffern und Konfidenz
        img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        text = f"{all_recognition_results[i]['extracted_digits']} ({all_recognition_results[i]['best_confidence']:.1f}%)"
        cv2.putText(img_color, text, (5, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        roi_display_images.append(img_color)
        
        # Adaptive Threshold anzeigen 
        img_adapt_color = cv2.cvtColor(roi_processed["adaptive"], cv2.COLOR_GRAY2BGR)
        cv2.putText(img_adapt_color, text, (5, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        roi_display_images.append(img_adapt_color)

    # Erstelle ein Gitter zum Anzeigen aller ROI-Bilder
    rows = 2
    cols = 6
    grid_h = rows * roi_images[0].shape[0]
    grid_w = cols * roi_images[0].shape[1]
    grid_image = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)

    # Platziere die Bilder im Gitter
    for i, img in enumerate(roi_display_images):
        if i >= rows * cols:
            break
        r, c = divmod(i, cols)
        h, w = roi_images[0].shape[:2]
        y, x = r * h, c * w
        
        # Resize falls nötig
        if img.shape[:2] != (h, w):
            img = cv2.resize(img, (w, h))
        
        # BGR konvertieren falls Grayscale
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        grid_image[y:y+h, x:x+w] = img

    cv2.imshow("Alle ROIs mit Erkennungen und Konfidenz", grid_image)
    cv2.imwrite("all_rois_grid_with_confidence.png", grid_image)

cv2.waitKey(0)  # Warte auf eine Taste
cv2.destroyAllWindows()  # Schließe alle Fenster 