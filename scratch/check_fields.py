import requests
import json

url = 'http://localhost:8042'
auth = ('orthanc', 'orthanc')

try:
    r = requests.get(f"{url}/studies", auth=auth)
    if r.status_code == 200 and r.json():
        study_id = r.json()[0]
        s_info = requests.get(f"{url}/studies/{study_id}", auth=auth).json()
        print(f"Study ID: {study_id}")
        print("Keys in Study info:")
        print(list(s_info.keys()))
        
        # Check if /studies/{id}/instances exists
        r_inst = requests.get(f"{url}/studies/{study_id}/instances", auth=auth)
        if r_inst.status_code == 200:
            print(f"Number of instances via /instances endpoint: {len(r_inst.json())}")
except Exception as e:
    print(f"Error: {e}")
