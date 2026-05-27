import requests
import json

url = 'http://localhost:8042'
user = 'orthanc'
pw = 'orthanc'

# Ambil satu study untuk testing
studies = requests.get(f"{url}/studies", auth=(user, pw)).json()
if studies:
    study_id = studies[0]
    print(f"Testing study: {study_id}")
    
    s_info = requests.get(f"{url}/studies/{study_id}", auth=(user, pw)).json()
    print("Study Keys:", s_info.keys())
    print("Series length:", len(s_info.get('Series', [])))
    
    series_resp = requests.get(f"{url}/studies/{study_id}/series", auth=(user, pw)).json()
    print("Series details type:", type(series_resp))
    if isinstance(series_resp, list) and len(series_resp) > 0:
        print("First series keys:", series_resp[0].keys())
        # Check if Instances is a key inside the series object
        print("Instances in series:", len(series_resp[0].get('Instances', [])))
else:
    print("No studies found.")
