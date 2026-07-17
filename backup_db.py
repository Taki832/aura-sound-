import os
import shutil
import time

def backup_database():
    db_file = "aurasound.db"
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    if not os.path.exists(db_file):
        print(f"[Backup Error] {db_file} does not exist.")
        return

    timestamp = int(time.time())
    backup_file = os.path.join(backup_dir, f"aurasound_backup_{timestamp}.db")
    
    shutil.copy2(db_file, backup_file)
    print(f"[Backup Successful] Created {backup_file}")

if __name__ == "__main__":
    backup_database()
