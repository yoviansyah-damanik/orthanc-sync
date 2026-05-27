import pydicom
import os

filepath = "C:/Orthanc/Worklists/PR202604200002.wl"
if os.path.exists(filepath):
    ds = pydicom.dcmread(filepath)
    print(ds)
else:
    print(f"File {filepath} not found")
