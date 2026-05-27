import requests
import json

url = 'http://localhost:8042'
user = 'orthanc'
pw = 'orthanc'

studies = requests.get(f"{url}/studies", auth=(user, pw)).json()
if studies:
    study_id = studies[0]
    series_resp = requests.get(f"{url}/studies/{study_id}/series", auth=(user, pw)).json()
    if series_resp:
        series_id = series_resp[0]['ID']
        # Fetch instances for this series
        instances_resp = requests.get(f"{url}/series/{series_id}/instances", auth=(user, pw)).json()
        print(f"Number of instances returned: {len(instances_resp)}")
        if len(instances_resp) > 0:
            print("First instance keys:", instances_resp[0].keys())
            tags = instances_resp[0].get('MainDicomTags', {})
            print("Instance MainDicomTags:", tags)
