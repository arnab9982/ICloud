import getpass
import json
import time
from urllib.parse import urlencode
from pyicloud import PyiCloudService

# --- CONFIGURATION ---
APPLE_ID = input("Enter your Apple ID email: ")
PASSWORD = getpass.getpass("Enter your Apple ID password: ")

print("\nConnecting to iCloud...")
api = PyiCloudService(APPLE_ID, PASSWORD)

# --- HANDLE TWO-FACTOR AUTHENTICATION (2FA) ---
if api.requires_2fa:
    print("\n[Action Required] Two-factor authentication required.")
    code = input("Enter the 6-digit verification code sent to your device: ")
    result = api.validate_2fa_code(code)
    if not result:
        print("Failed to verify code. Exiting.")
        exit(1)
    
    if api.is_trusted_session:
        print("Session trusted successfully.")

# --- FETCH ALL MEDIA ---
print("\nFetching your media library. This might take a moment...")
all_media = api.photos.all
total_files = len(all_media)
print(f"Found {total_files} total photos and videos to move to trash.")

# Set up internal deletion API endpoints
delete_url = f"{api.photos.service_endpoint}/records/modify?{urlencode(api.photos.params)}"
delete_headers = {'Content-type': 'text/plain'}

operations = []
seen_record_names = set()
count = 0

print("\nBeginning automated batch trashing...")

for item in all_media:
    try:
        # Safe extraction for CKRecord object properties
        asset = item._asset_record
        if hasattr(asset, 'recordName'):
            record_name = asset.recordName
            record_tag = asset.recordChangeTag
        elif hasattr(asset, 'record_name'):
            record_name = asset.record_name
            record_tag = asset.record_change_tag
        elif isinstance(asset, dict):
            record_name = asset.get('recordName')
            record_tag = asset.get('recordChangeTag')
        else:
            record_name = getattr(asset, 'recordName', None) or getattr(asset, 'record_name', None)
            record_tag = getattr(asset, 'recordChangeTag', None) or getattr(asset, 'record_change_tag', None)

        if not record_name:
            continue

        if record_name in seen_record_names:
            continue
        seen_record_names.add(record_name)
        
        modify_record = {
            "fields": {"isDeleted": {"value": 1}},
            "recordChangeTag": record_tag,
            "recordName": record_name,
            "recordType": "CPLAsset"
        }
        
        op = {
            "operationType": "update",
            "record": modify_record
        }
        operations.append(op)
        count += 1
        
        if len(operations) >= 100:
            post_data = json.dumps({
                "atomic": True,
                "desiredKeys": ["isDeleted"],
                "operations": operations,
                "zoneID": {"zoneName": "PrimarySync"}
            })
            
            response = api.photos.session.post(delete_url, data=post_data, headers=delete_headers)
            if response.status_code == 200:
                print(f"[{count}/{total_files}] Successfully trashed batch of 100 items.")
            else:
                print(f"[Warning] Batch failed with API status {response.status_code}")
                
            operations = []  
            time.sleep(2)    
            
    except Exception as e:
        print(f"Skipping an item due to data mapping error: {e}")

if operations:
    post_data = json.dumps({
        "atomic": True,
        "desiredKeys": ["isDeleted"],
        "operations": operations,
        "zoneID": {"zoneName": "PrimarySync"}
    })
    response = api.photos.session.post(delete_url, data=post_data, headers=delete_headers)
    if response.status_code == 200:
        print(f"[{count}/{total_files}] Successfully trashed final batch of {len(operations)} items.")
    else:
        print(f"[Warning] Final batch failed with API status {response.status_code}")

print("\nScript tasks completed successfully!")