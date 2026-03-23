import os
import requests
import re
from dotenv import load_dotenv
from PIL import Image, ImageDraw
import math

# Load environment variables from .env file in the parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

# URLs
url_login = "https://www.hackthissite.org/user/login"
url_mission = "https://www.hackthissite.org/missions/prog/6/"
url_image_page = f"{url_mission}image/"

# Get credentials from environment variables
payload = {
    "username": os.getenv("HTS_USERNAME"),
    "password": os.getenv("HTS_PASSWORD")
}

# Headers for the request
headers = {
    "Referer": "https://www.hackthissite.org/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- Python implementation of the JavaScript drawing functions ---

def draw_line_py(draw, x1, y1, x2, y2):
    """ Replicates the Bresenham's line algorithm from the JS code. """
    draw.line([(x1, y1), (x2, y2)], fill="green", width=1)

def draw_arc_py(draw, x, y, r, s, e):
    """ Replicates the arc drawing logic from the JS code. """
    # The JS code draws an arc by plotting individual pixels.
    # PIL's arc drawing is more efficient.
    # JS uses degrees, PIL uses degrees. JS angle goes counter-clockwise from 3 o'clock.
    # PIL's default is the same.
    # JS calculates end angle by s + e.
    start_angle = s
    end_angle = s + e
    
    # The JS code iterates with a step of 8 degrees, which is very coarse.
    # We can simulate this by drawing points or just draw the full arc.
    # Let's draw points to be more faithful to the original.
    torad = math.pi / 180
    for angle in range(start_angle, end_angle + 1, 1): # Step 1 for smoother arc
        rad = angle * torad
        xx = round(x + r * math.cos(rad))
        yy = round(y - r * math.sin(rad)) # In graphics, Y is often inverted.
        draw.point((xx, yy), fill="green")

# --- Main script ---

with requests.Session() as session:
    # 1. Login
    try:
        print("Logging in...")
        login_response = session.post(url_login, data=payload, headers=headers)
        login_response.raise_for_status()
        print("Login successful.")
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        exit()

    # 2. Visit the main mission page first to establish session state
    try:
        print(f"Accessing main mission page: {url_mission}")
        session.get(url_mission, headers=headers).raise_for_status()
        print("Main mission page accessed.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to access main mission page: {e}")
        exit()

    # 3. Fetch the HTML page with the JavaScript code
    try:
        print(f"Fetching drawing data from: {url_image_page}")
        html_response = session.get(url_image_page)
        html_response.raise_for_status()
        
        # Check if response is empty
        if not html_response.text.strip():
            print("Server returned an empty response. Aborting.")
            exit()

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch image page: {e}")
        exit()

    # 4. Extract the drawData array
    match = re.search(r'var drawData = new Array\((.*?)\);', html_response.text, re.DOTALL)
    if not match:
        print("Could not find 'drawData' array in the HTML source.")
        # Save the received HTML for debugging purposes
        debug_file_path = os.path.join(os.path.dirname(__file__), 'debug_page.html')
        with open(debug_file_path, 'w', encoding='utf-8') as f:
            f.write(html_response.text)
        print(f"HTML content saved to {debug_file_path} for debugging.")
        exit()

    try:
        draw_data_str = match.group(1)
        draw_data = [int(x) for x in draw_data_str.split(',')]
        print(f"Successfully extracted {len(draw_data)} drawing commands.")
    except ValueError as e:
        print(f"Failed to parse drawData: {e}")
        exit()

    # 5. Create an image and process the drawing commands
    # Determine image size by finding max coordinates, or use a sufficiently large canvas.
    # A quick scan of the data shows coordinates up to ~850, so 900x900 should be safe.
    img_size = (900, 900)
    img = Image.new('RGB', img_size, 'black')
    draw = ImageDraw.Draw(img)

    print("Processing drawing commands and building image...")
    i = 0
    while i < len(draw_data):
        # Check if it's a line or an arc command
        # This check must be done carefully to avoid index out of bounds
        if i + 2 >= len(draw_data):
            break # Not enough data for a full command

        if draw_data[i+2] >= 10: # It's a line
            if i + 3 >= len(draw_data):
                break # Not enough data for a line
            x1, y1, x2, y2 = draw_data[i], draw_data[i+1], draw_data[i+2], draw_data[i+3]
            draw_line_py(draw, x1, y1, x2, y2)
            i += 4
        else: # It's an arc
            if i + 4 >= len(draw_data):
                break # Not enough data for an arc
            x, y, r, s, e = draw_data[i], draw_data[i+1], draw_data[i+2], draw_data[i+3], draw_data[i+4]
            draw_arc_py(draw, x, y, r, s, e)
            i += 5
    
    # 6. Save the final image
    try:
        image_path = os.path.join(os.path.dirname(__file__), 'image.png')
        img.save(image_path)
        print(f"Image successfully created and saved to {image_path}")
    except IOError as e:
        print(f"Failed to save image: {e}")
