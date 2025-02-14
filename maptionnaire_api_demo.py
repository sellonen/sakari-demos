import http.client
import json
import csv
import io
from contextlib import contextmanager
import sys
import termios
import tty

server = "app.maptionnaire.com"
headers = {
    'Content-type': 'application/json',
}

email = "sakari+apidemo@maptionnaire.com"

def getpass(prompt="Password: "):
    """Gets password input without echoing."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        print(prompt, end="", flush=True)  # Print prompt without newline
        password = ""
        while True:
            char = sys.stdin.read(1)
            if char == '\n':
                break
            if char == '\r': # Handle carriage return as well
                break
            if char == '\x7f': # Handle backspace (ASCII 127)
                if password:
                    password = password[:-1]
                    print("\b \b", end="", flush=True) # Move cursor back, overwrite with space
                continue
            password += char
            print("*", end="", flush=True)  # Print asterisk for each character
        print() # Newline after password input
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return password


password = getpass("Enter your Maptionnaire password: ")

login_payload = {
    "emailAddress": email,
    "password": password
}


# Vanilla python helper methods, but in your own scripts,
# please use python requests or similar: https://requests.readthedocs.io/en/latest/
@contextmanager
def https_connection(server, context=None):
    conn = http.client.HTTPSConnection(server, context=context)
    try:
        yield conn
    finally:
        conn.close()

def do_post(endpoint, payload):
    with https_connection(server) as conn:
        json_payload = json.dumps(payload)
        conn.request("POST", endpoint, body=json_payload, headers=headers)
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        if response.status >= 400:
            raise Exception(f"Got error response: {data}")
        return data

# Login and save the authorization headers
login_response = do_post("/v1/auth/login", login_payload)
session_id = json.loads(login_response)["response"]["sessionId"]
headers["Authorization"] = f"Bearer {session_id}"

# Download the data
responses_str = do_post("/v1/questionnaire/response/export/csv", {"questionnaireId": "3it4s3ew32ja"})
respondents_str = do_post("/v1/questionnaire/respondent/export/csv", {"questionnaireId": "3it4s3ew32ja"})

# Parse the data into dicts which look like this:
# respondents = {
#     "3gld8ewr7gx3": {
#         "Respondent ID": "3gld8ewr7gx3",
#         "responses": [
#             {
#                 "Index": "1",
#                 "Element ID": "d9de8d17-4438-4483-96a7-0bb7b35d751b",
#                 "Element Label": "What is so special about this place?",
#                 "Content": "Good urban vibes!",
#             },
#             {
#                 "Index": "1",
#                 "Element ID": "6c3a0b1c-dada-44c9-9ef2-32697d59962a",
#                 "Element Label": "Response 1 for drawbutton 6c3a0b1c-dada-44c9-9ef2-32697d59962a",
#                 "Content": "60.163313,24.941655",
#             },
#             {
#                 "Index": "0",
#                 "Element ID": "d9de8d17-4438-4483-96a7-0bb7b35d751b",
#                 "Element Label": "What is so special about this place?",
#                 "Content": "Such great views",
#             },
#             {
#                 "Index": "0",
#                 "Element ID": "6c3a0b1c-dada-44c9-9ef2-32697d59962a",
#                 "Element Label": "Response 0 for drawbutton 6c3a0b1c-dada-44c9-9ef2-32697d59962a",
#                 "Content": "60.186576,24.904174",
#             },
#             {
#                 "Element ID": "66f8616d-9291-4bac-adec-b52b62489dea",
#                 "Element Label": "How old are you?: Young",
#                 "Content": "0",
#             },
#             {
#                 "Element ID": "c234c050-bffe-44bd-b41e-57ff01abc075",
#                 "Element Label": "Choose pseudonym",
#                 "Content": "Saku",
#             }
#         ]
#     },
# }
responses_reader = csv.DictReader(io.StringIO(responses_str))
respondents_reader = csv.DictReader(io.StringIO(respondents_str))
respondents = { row["Respondent ID"]: row for row in respondents_reader }
for row in responses_reader:
    respondent_id = row["Respondent ID"]
    respondent = respondents[respondent_id]
    if "responses" not in respondent:
        respondent["responses"] = []
    respondent["responses"].append(row)


# Get these IDs with 
# publication = do_post("/v1/questionnaire/publication/view", {"questionnaireId":"3it4s3ew32ja"})
element_ids = {
    "pseudonym": "c234c050-bffe-44bd-b41e-57ff01abc075",
    "age": "66f8616d-9291-4bac-adec-b52b62489dea",
    "favorite_place_coordinates": "6c3a0b1c-dada-44c9-9ef2-32697d59962a",
    "favorite_place_reason": "d9de8d17-4438-4483-96a7-0bb7b35d751b",
}

# Print out the data into console
print("\n")
for respondent in respondents.values():
    age = None
    pseudonym = None
    favorite_places = {}
    if "responses" not in respondent:
        continue # Someone has just visited the survey, not actually responded anything
    for response in respondent["responses"]:
        if response["Element ID"] == element_ids["age"]:
            if response["Content"] == "0":
                age = "young"
            elif response["Content"] == "1":
                age = "old"
        if response["Element ID"] == element_ids["pseudonym"]:
            pseudonym = response["Content"]
        if response["Element ID"] == element_ids["favorite_place_coordinates"]:
            if response["Index"] not in favorite_places:
                favorite_places[response["Index"]] = {}    
            favorite_places[response["Index"]]["coordinates"] = response["Content"]
        if response["Element ID"] == element_ids["favorite_place_reason"]:
            if response["Index"] not in favorite_places:
                favorite_places[response["Index"]] = {}    
            favorite_places[response["Index"]]["reason"] = response["Content"]
    print(f"Respondent '{pseudonym}' thinks they are {age}.")
    if not favorite_places:
        continue
    print(f"Their favorite places are the following:")
    for place in favorite_places.values():
        print(f"\tLocation: {place.get('coordinates')}")
        print(f"\tReason: {place.get('reason')}")