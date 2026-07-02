import os
import getpass
import time
from datetime import datetime
from pyicloud import PyiCloudService

# --- CONFIGURATION ---
APPLE_ID = input("Enter your Apple ID email: ")
PASSWORD = getpass.getpass("Enter your Apple ID password: ")
# Paste the exact path to your external hard drive folder below
BACKUP_DIR = input(r"Enter the full local/external drive path for backup: ").strip()

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

# --- FETCH ALL MEDIA (PHOTOS & VIDEOS) ---
print("\nFetching your media library. This may take a few minutes for large libraries...")
# api.photos.all contains both photos and video files seamlessly
all_media = api.photos.all
total_files = len(all_media)
print(f"Found {total_files} total photos and videos in your iCloud library.")

# Loop through all items
for index, item in enumerate(all_media, start=1):
    filename = item.filename
    
    # 1. Get creation date to organize into Year/Month folders
    try:
        created_date = item.created
        if created_date:
            year_folder = created_date.strftime("%Y")
            month_folder = created_date.strftime("%m-%B") # e.g., "07-July"
        else:
            year_folder, month_folder = "Unknown_Year", "Unknown_Month"
    except Exception:
        year_folder, month_folder = "Unknown_Year", "Unknown_Month"
        
    # 2. Build the structured folder path on your external drive
    target_folder = os.path.join(BACKUP_DIR, year_folder, month_folder)
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        
    save_path = os.path.join(target_folder, filename)
    
    # 3. Skip if already downloaded
    if os.path.exists(save_path):
        print(f"[{index}/{total_files}] Skipping (Exists): {year_folder}/{month_folder}/{filename}")
        continue
        
    # 4. Download file (handles standard bytes, streams, and includes a retry mechanism)
    print(f"[{index}/{total_files}] Downloading: {year_folder}/{month_folder}/{filename}...")
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            download = item.download()
            if download is None:
                raise Exception("iCloud returned an empty download object.")
            
            with open(save_path, 'wb') as opened_file:
                # Case A: Downloaded object is a direct bytes array (common for photos)
                if isinstance(download, bytes):
                    opened_file.write(download)
                
                # Case B: Downloaded object is a stream (common for large videos)
                elif hasattr(download, 'iter_content'):
                    for chunk in download.iter_content(chunk_size=8192):
                        if chunk:
                            opened_file.write(chunk)
                
                # Case C: Fallback for older pyicloud raw streams
                elif hasattr(download, 'raw'):
                    opened_file.write(download.raw.read())
                
                # Case D: Final catch-all fallback
                else:
                    opened_file.write(download.content if hasattr(download, 'content') else download)
            
            # Break out of the retry loop if download succeeds
            break
            
        except Exception as e:
            if attempt < max_retries:
                print(f"   [Retry {attempt}/{max_retries}] Connection interrupted. Retrying in 3 seconds... ({e})")
                time.sleep(3)
            else:
                print(f"   [ERROR] Failed to download {filename} after {max_retries} attempts: {e}")
                # Clean up incomplete or corrupted files so it can retry fresh next time
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass

print(f"\nBackup complete! Your sorted files are saved at: {os.path.abspath(BACKUP_DIR)}")