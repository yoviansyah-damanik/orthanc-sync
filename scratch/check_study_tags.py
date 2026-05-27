import requests
import json

url = 'http://localhost:8042'
user = 'orthanc'
pw = 'orthanc'

studies = requests.get(f"{url}/studies", auth=(user, pw)).json()
if studies:
    study_id = studies[0]
    s_info = requests.get(f"{url}/studies/{study_id}", auth=(user, pw)).json()
    print("MainDicomTags:", json.dumps(s_info.get('MainDicomTags', {}), indent=2))
