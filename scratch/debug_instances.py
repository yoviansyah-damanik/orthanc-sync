import requests
import json

url = 'http://localhost:8042'
auth = ('orthanc', 'orthanc')

try:
    r = requests.get(f"{url}/instances", auth=auth)
    if r.status_code == 200:
        instance_ids = r.json()
        print(f"Total instances in Orthanc: {len(instance_ids)}")
        last_10 = instance_ids[-10:]
        for iid in last_10:
            i_info = requests.get(f"{url}/instances/{iid}", auth=auth).json()
            p_info = requests.get(f"{url}/instances/{iid}/patient", auth=auth).json()
            s_info = requests.get(f"{url}/instances/{iid}/study", auth=auth).json()
            print(f"\nInstance: {iid}")
            print(f"Patient Name: {p_info.get('MainDicomTags', {}).get('PatientName', 'UNKNOWN')}")
            print(f"AccessionNumber: {s_info.get('MainDicomTags', {}).get('AccessionNumber', 'UNKNOWN')}")
            print(f"StudyInstanceUID: {s_info.get('MainDicomTags', {}).get('StudyInstanceUID', 'UNKNOWN')}")
except Exception as e:
    print(f"Error: {e}")
