import os
import requests
import re
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

url_login = "https://www.hackthissite.org/user/login"
url_objective = "https://www.hackthissite.org/missions/prog/12/index.php"

# Credentials loaded from .env
payload = {
	"password": os.getenv("HTS_PASSWORD"),
	"username": os.getenv("HTS_USERNAME")
}

# Need this extra header to work
headers = {"Referer": "https://www.hackthissite.org/"}


# Open session and login
session = requests.Session()
session.post(url=url_login, data=payload, headers=headers)
result = session.get(url_objective)

# Take the string to parse
string = re.search('<b>String: </b><input type="text" value="(.+)" />', result.text).group(1)

# Prepare the terrain...
composite = 0
prime = 0
characters = ""

# Some algorithm math
for a in string:
	if a.isdigit():
		if a == '4' or a == '6' or a == '8' or a == '9':
			composite += int(a)
		elif a == '2' or a == '3' or a == '5' or a == '7':
			prime += int(a)
	elif len(characters) < 25:
		characters += chr(ord(a)+1)

result = characters + str(composite*prime)

# Send solution
payload = {"solution": result, "submitbutton": ""}
session.post(url=url_objective, data=payload, headers=headers)
session.close()
