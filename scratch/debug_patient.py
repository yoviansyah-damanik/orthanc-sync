import requests
import json

url = 'http://localhost:8042'
auth = ('orthanc', 'orthanc')

patient_id = '042790'

query = {
    "Level": "Study",
    "Query": {"PatientID": patient_id}
}

try:
    r = requests.post(f"{url}/tools/find", auth=auth, json=query)
    print(f"Query for PatientID {patient_id}:")
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.json()}")
    
    if r.status_code == 200 and r.json():
        for study_id in r.json():
            s_info = requests.get(f"{url}/studies/{study_id}", auth=auth).json()
            print(f"\nStudy ID: {study_id}")
            print(f"Instances Count: {len(s_info.get('Instances', []))}")
            print(f"Main Dicom Tags: {s_info.get('MainDicomTags', {})}")
            print(f"AccessionNumber: {s_info.get('MainDicomTags', {}).get('AccessionNumber', 'NONE')}")
except Exception as e:
    print(f"Error: {e}")
