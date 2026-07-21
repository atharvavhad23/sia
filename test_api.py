import requests

url = "http://127.0.0.1:8000/api/v1/extract"
files = {'file': open('04_Atharva_9.pdf', 'rb')}
data = {'engine': 'hybrid'}

try:
    response = requests.post(url, files=files, data=data)
    print("Status Code:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
