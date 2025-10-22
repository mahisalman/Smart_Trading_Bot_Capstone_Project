import base64
import json
import os
import requests
import subprocess
import sys

# --- CONFIG ---
IMG_PATH = "firefox_tab_capture.png"
OUTPUT_JSON = "latest_signal.json"   # 👈 JSON file to save result
API_MODEL = "gemini-2.5-flash-preview-05-20"

apiKey = "AIzaSyBjgSGvrOy7uDB7YwK6Qzba0iMk5aZ4b3g"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{API_MODEL}:generateContent?key={apiKey}"


def run_chrome_shot():
    """Run chrome_shot.py to capture the latest Firefox tab."""
    script_path = r"f:\cap\chrome_shot.py"
    print("🚀 Running chrome_shot.py to capture chart...")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        if result.returncode != 0:
            print(f"❌ Error running chrome_shot.py:\n{result.stderr}")
            return False
        print("✅ Screenshot captured successfully.")
        return True
    except Exception as e:
        print(f"⚠️ Failed to run chrome_shot.py: {e}")
        return False


def image_to_base64(image_path):
    """Convert a local image file to base64 string."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except IOError as e:
        print(f"Error reading image file: {e}")
        return None


def find_latest_signal_llm(base64_image):
    """Send image to Gemini API and find the latest trading signal."""
    prompt = (
        "Analyze the provided trading chart image. Look for the signals 'BUY' and 'SELL'. "
        "Return only the one that is **furthest to the right** (latest). "
        "Respond with only the word 'BUY' or 'SELL'. "
        "Also detect BUY and SELL price positions and ORH/ORL from the right side."
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64_image
                        }
                    }
                ]
            }
        ]
    }

    print("📤 Sending image to Gemini Vision API...")

    try:
        response = requests.post(
            API_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        response.raise_for_status()

        result = response.json()
        candidate = result.get("candidates", [{}])[0]
        signal_text = (
            candidate.get("content", {})
            .get("parts", [{}])[0]
            .get("text", "Signal Not Found")
            .strip()
        )
        return signal_text

    except requests.exceptions.RequestException as e:
        print(f"API Request Failed: {e}")
        return "API_ERROR"
    except Exception as e:
        print(f"Error processing API response: {e}")
        return "RESPONSE_ERROR"


def save_signal_to_json(signal):
    """💾 Save the detected signal to a JSON file."""
    data = {
        "Chart_signal": signal
        #"image_used": IMG_PATH
    }
    try:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"💾 Signal saved to {OUTPUT_JSON}")
    except Exception as e:
        print(f"⚠️ Error saving JSON: {e}")


def main():
    # Step 1️⃣: Capture new chart image
    if not run_chrome_shot():
        print("⚠️ Screenshot step failed. Skipping signal detection.")
        save_signal_to_json("None")
        return

    # Step 2️⃣: Check if image exists
    if not os.path.exists(IMG_PATH):
        print(f"Screenshot not found: {IMG_PATH}")
        save_signal_to_json("None")
        return

    # Step 3️⃣: Convert image
    base64_img = image_to_base64(IMG_PATH)
    if not base64_img:
        save_signal_to_json("None")
        return

    # Step 4️⃣: Analyze with Gemini
    latest_signal = find_latest_signal_llm(base64_img)

    # Step 5️⃣: Print and save
    print("\n--- Latest Trading Signal Detected ---")
    print(f"Chart_Signal: {latest_signal}")
    print("--------------------------------------")

    save_signal_to_json(latest_signal)


if __name__ == "__main__":
    main()
