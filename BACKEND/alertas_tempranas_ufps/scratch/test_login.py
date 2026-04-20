import requests
import json

url = "http://localhost:8000/api/usuarios/login/"
payload = {
    "email": "andreadelpilarbr@ufps.edu.co",
    "password": "06733"
}
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
