import os
import requests
import re
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

url_login = "https://www.hackthissite.org/user/login"
url_objective = "https://www.hackthissite.org/missions/prog/11/"

# Credentials loaded from .env
payload = {
	"username": os.getenv("HTS_USERNAME"),
	"password": os.getenv("HTS_PASSWORD")
}

# Need this extra header to work
headers = {"Referer": "https://www.hackthissite.org/"}


# Open session and login
session = requests.Session()
login_resp = session.post(url=url_login, data=payload, headers=headers)
print(f"Login status: {login_resp.status_code}")

result = session.get(url_objective)
print(f"Page status: {result.status_code}")

# Take both string and shift from the html
# Separator changes each time (comma, dot, slash, apostrophe, etc.)
# So we grab everything between "Generated String: " and "<br" then extract digits
char_match = re.findall(r"Generated String: (.+?)<br", result.text)
shift_match = re.findall(r"Shift: (-?\d+)", result.text)

if not char_match or not shift_match:
    print("Could not find Generated String or Shift on the page.")
    print("You may not be logged in, or the challenge page has changed.")
    session.close()
    exit(1)

characters = char_match[0]
shift = int(shift_match[0])
print(f"Generated String: {characters}")
print(f"Shift: {shift}")

# Algorithm: extract all numbers, subtract shift, convert to ASCII chars
nums = [int(x) for x in re.findall(r'\d+', characters)]
result_text = ''.join(chr(n - shift) for n in nums)
print(f"Decoded: {result_text}")

# Send solution
payload = {"solution": result_text}
resp = session.post(url=url_objective, data=payload, headers=headers)

# Check if solution was accepted
if 'Congratulations' in resp.text or 'correct' in resp.text.lower():
    print("Solution accepted!")
else:
    print("Solution submitted.")
session.close()