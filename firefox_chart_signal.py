import base64
import json
import os
import requests

# --- CONFIG ---
IMG_PATH = "firefox_tab_capture.png"
API_MODEL = "gemini-2.5-flash-preview-05-20"
# NOTE: The apiKey variable is intentionally left empty. 
# It will be provided by the execution environment at runtime.
apiKey = "AIzaSyBjgSGvrOy7uDB7YwK6Qzba0iMk5aZ4b3g" 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{API_MODEL}:generateContent?key={apiKey}"


def image_to_base64(image_path):
    """Converts a local image file to a base64 string."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except IOError as e:
        print(f"Error reading image file: {e}")
        return None

def find_latest_signal_llm(base64_image):
    """
    Calls the Gemini API to analyze the image and find the latest (rightmost) signal.
    """
    
    # 1. Define the specific prompt for the vision model
    prompt = (
        "Analyze the provided trading chart image. Look for the visible signals 'A' and 'Y'. "
        "Your task is to identify and return only the text of the signal that is **furthest to the right** on the chart (the latest signal). "
        "Respond with only the word 'A' or 'Y"
        "Also find the buy position from the right side of the chart. and return only the price value like 1.23456 or 1234.56."
        "same for the sell position from the right side of the chart."
        "And also mention the ORH and ORL position from the right side of the chart. and show in the output as veriables."
        "Consider the 'A' as BUY signal and 'Y' as SELL signal."
       )
    
    # 2. Construct the API payload with text prompt and image data
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

    print("Sending image data to Gemini Vision for analysis...")
    
    try:
        response = requests.post(
            API_URL, 
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload)
        )
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        result = response.json()
        
        # 3. Extract the clean signal text
        candidate = result.get('candidates', [{}])[0]
        signal_text = candidate.get('content', {}).get('parts', [{}])[0].get('text', 'Signal Not Found').strip().upper()
        
        return signal_text

    except requests.exceptions.RequestException as e:
        print(f"API Request Failed: {e}")
        return "API_ERROR"
    except Exception as e:
        print(f"Error processing API response: {e}")
        return "RESPONSE_ERROR"


def main():
    if not os.path.exists(IMG_PATH):
        print(f"Screenshot file not found: '{IMG_PATH}'")
        print("Please ensure the image is in the same folder.")
        return

    # Convert the image to Base64 format
    base64_image_data = image_to_base64(IMG_PATH)
    if not base64_image_data:
        return

    # Get the signal using the LLM
    latest_signal = find_latest_signal_llm(base64_image_data)

    print("\n--- Latest Trading Signal Detected via LLM Vision ---")
    print(f"Chart_Signal: {latest_signal}")
    print("-----------------------------------------------------")


if __name__ == "__main__":
    main()
