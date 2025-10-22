# TradingView Chart Data Extractor

A lightweight Python utility that reads a TradingView chart screenshot and extracts:

- **OCR text** from the whole image  
- **Y‑axis** and **X‑axis** labels  
- **Candlestick** data (green/red bodies)  
- **Indicator zones** (e.g., volume, MACD panels)

```
mnt/
└─ data/
   └─ extract_chart.py   # ← Main extraction script
README.md                # This file
```

## 🛠️ Prerequisites

1. **Python 3.8+**
     pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
     ```

3. **Python packages** (install via `pip`):

   ```sh
   pip install opencv-python pytesseract numpy scikit-image
   ```

## 🚀 Quick Start

```sh
# Navigate to the project folder
cd f:\cap

# Install dependencies
pip install -r requirements.txt   # (optional, if you create a requirements file)

# Run the extractor
python mnt\data\extract_chart.py --image path\to\chart.png --out output_folder
```

### Arguments

| Argument | Description | Required |
## 📄 Output

The script creates the following files inside the output folder:

- `result.json` – Full extraction data (image path, size, OCR text, axis labels, candles, indicator zones).  
- `candles_debug.png` – Image with detected candle bounding boxes.  
- `zones_debug.png` – Image with detected indicator zones highlighted.  
- `ocr_full.txt` – Plain OCR text extracted from the whole image.

### Sample `result.json` structure

```json
{
  "image": "path/to/chart.png",
  "size": { "width": 1280, "height": 720 },
  "ocr_text": "Sample OCR output …",
  "y_axis_labels": [
    { "bbox": [1200, 10, 1250, 30], "text": "1234" }
  ],
  "x_axis_labels": [
    { "bbox": [100, 700, 150, 720], "text": "12:00" }
  ],
  "candles": [
    { "color": "green", "bbox": [100, 200, 120, 250], "area": 500 },
    { "color": "red",   "bbox": [130, 210, 150, 260], "area": 480 }
  ],
    { "bbox": [0, 600, 1280, 720], "area": 92160 }
  ]
```


- **No OCR output?**  
  Ensure the image has sufficient contrast. Adjust the preprocessing step in `ocr_text` if needed.

- **Candles not detected?**  
  The HSV colour ranges may need tweaking for different chart themes. Modify `lower_green`, `upper_green`, `lower_red1`, etc., in `detect_candles`.
- **Tesseract not found**  
  Verify the `tesseract_cmd` path matches your installation or add Tesseract to your system `PATH`.
TradingView Chart Data Extractor
================================

This repository contains a single script **`extract_chart.py`** that extracts useful
information from a TradingView screenshot.

Features
--------
* Full‑image OCR (Tesseract) – extracts the raw text of the chart.
* Detection of Y‑axis and X‑axis labels.
* Candle detection (green / red) with visual debug image.
* Indicator‑zone detection.
* **Open‑Range High (ORH) and Open‑Range Low (ORL)** detection.
  * First tries Tesseract OCR.
  * If the values are not found, falls back to a Hugging Face model
    (`microsoft/trocr-base-handwritten`).
* Results are saved as:
  * `result.json` – comprehensive JSON payload.
  * `orh.txt` and `orl.txt` – plain‑text files containing the numeric values.
  * `candles_debug.png` and `zones_debug.png` – visual debugging images.

Prerequisites
-------------
1. **Python 3.8+**
2. **Tesseract OCR** installed and the path set correctly in the script:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```
3. Required Python packages – they will be installed automatically on first run,
   but you can also install them manually:
   ```bash
   pip install opencv-python pytesseract numpy scikit-image transformers torch pillow
   ```

Usage
-----
```bash
python extract_chart.py --image path/to/chart.png [--out output_folder]
```

* `--image` – path to the TradingView screenshot (required).
* `--out`   – folder where all results will be written (default: `chart_output`).

Example
~~~~~~~
```bash
python extract_chart.py --image samples/firefox_tab_capture.png
```
After execution you will find the JSON result and the `orh.txt` / `orl.txt`
files inside the output directory.

License
-------
MIT – see the `LICENSE` file if you add one.

---
Feel free to modify the script to suit your own chart‑type or add more
post‑processing steps. Happy hacking!

## 📜 License

This project is released under the MIT License – feel free to modify and redistribute.

--- 

*Generated for the workspace containing `extract_chart.py`.*