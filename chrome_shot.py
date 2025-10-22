import pyautogui
import pygetwindow as gw
import time
import os

def capture_firefox_tab_content(filename="firefox_tab_content.png"):
    """
    Captures only the visible content area of the active Firefox tab.
    Make sure Firefox is open and visible on the screen.
    """

    print("Searching for an open Firefox window...")

    all_windows = gw.getAllTitles()
    firefox_windows = [title for title in all_windows if "Mozilla Firefox" in title or "Firefox" in title]

    if not firefox_windows:
        print("No open Firefox window found. Please open Mozilla Firefox and try again.")
        for title in all_windows[:8]:
            if title.strip():
                print(f" - {title}")
        return

    # Use the first found Firefox window
    window_title = firefox_windows[0]
    window = gw.getWindowsWithTitle(window_title)[0]

    # print(f"Found Firefox window: {window.title}")
    print(f"Found Firefox window: {window.title.encode('ascii', 'ignore').decode()}")

    window.activate()
    time.sleep(1)  # allow time to focus

    # Get window geometry
    left, top, width, height = window.left, window.top, window.width, window.height

    # Adjust for title bar and browser chrome
    title_bar_height = 85   # top toolbar + address bar height (adjust if needed)
    bottom_padding = 10     # exclude bottom window border

    # Define inner tab region
    content_top = top + title_bar_height
    content_height = height - title_bar_height - bottom_padding

    print(f"Inner tab area: left={left}, top={content_top}, width={width}, height={content_height}")

    # Capture only the tab content
    screenshot = pyautogui.screenshot(region=(left, content_top, width, content_height))
    screenshot.save(filename)

    full_path = os.path.abspath(filename)
    print(f"\nCaptured Firefox tab content successfully!")
    print(f"Saved to: {full_path}")


if __name__ == "__main__":
    capture_firefox_tab_content("firefox_tab_capture.png")
