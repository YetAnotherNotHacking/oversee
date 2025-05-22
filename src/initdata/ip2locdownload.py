import requests
import zipfile
import os

def download_database(DB_URL, DB_ZIP, DB_CSV):
    if os.path.exists(DB_ZIP):
        return
    if not os.path.exists(DB_ZIP):
        r = requests.get(DB_URL)
        with open(DB_ZIP, "wb") as f:
            f.write(r.content)

def extract_database(DB_CSV, DB_ZIP):
    if os.path.exists(DB_CSV):
        return
    with zipfile.ZipFile(DB_ZIP, 'r') as zip_ref:
        zip_ref.extract(DB_CSV)