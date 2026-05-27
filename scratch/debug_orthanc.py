import requests
import json

url = 'http://localhost:8042'
auth = ('orthanc', 'orthanc')

accession_number = 'US20260214000001'

query = {
    "Level": "Study",
    "Query": {"AccessionNumber": accession_number}
}

try:
    r = requests.post(f"{url}/tools/find", auth=auth, json=query)
    print(f"Query for {accession_number}:")
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.json()}")
    
    if r.status_code == 200 and r.json():
        for study_id in r.json():
            s_info = requests.get(f"{url}/studies/{study_id}", auth=auth).json()
            print(f"Study ID: {study_id}")
            print(f"Instances Count: {len(s_info.get('Instances', []))}")
            print(f"Main Dicom Tags: {s_info.get('MainDicomTags', {})}")
    else:
        # Try finding all studies to see what accession numbers are there
        print("\nListing last 5 studies to check formatting:")
        r = requests.get(f"{url}/studies", auth=auth)
        if r.status_code == 200:
            study_ids = r.json()[-5:]
            for sid in study_ids:
                s_info = requests.get(f"{url}/studies/{sid}", auth=auth).json()
                print(f"ID: {sid}, AccessionNumber: {s_info.get('MainDicomTags', {}).get('AccessionNumber', 'NONE')}")
except Exception as e:
    print(f"Error: {e}")
