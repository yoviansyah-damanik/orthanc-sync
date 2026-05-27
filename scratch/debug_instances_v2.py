import requests
import json

url = 'http://localhost:8042'
auth = ('orthanc', 'orthanc')

try:
    r = requests.get(f"{url}/instances", auth=auth)
    if r.status_code == 200:
        instance_ids = r.json()
        print(f"Total instances in Orthanc: {len(instance_ids)}")
        for iid in instance_ids:
            i_info = requests.get(f"{url}/instances/{iid}", auth=auth).json()
            s_info = requests.get(f"{url}/instances/{iid}/study", auth=auth).json()
            print(f"\nInstance: {iid}")
            print(f"Study ID: {s_info.get('ID')}")
            print(f"AccessionNumber: {s_info.get('MainDicomTags', {}).get('AccessionNumber', 'UNKNOWN')}")
            print(f"Study Instance Count: {len(s_info.get('Instances', []))}")
except Exception as e:
    print(f"Error: {e}")
