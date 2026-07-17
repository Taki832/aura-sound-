import os
import time
import uuid

# StorageService abstraction
# Designed to be easily swapped with Cloudflare R2, AWS S3, or Supabase Storage later.

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'web', 'uploads')
AVATARS_DIR = os.path.join(UPLOAD_DIR, 'avatars')
BANNERS_DIR = os.path.join(UPLOAD_DIR, 'banners')

# Ensure directories exist
os.makedirs(AVATARS_DIR, exist_ok=True)
os.makedirs(BANNERS_DIR, exist_ok=True)

class StorageService:
    @staticmethod
    async def uploadAvatar(user_id: int, image_bytes: bytes, ext: str = 'jpg') -> str:
        """Saves avatar to disk and returns the relative URL path."""
        filename = f"{user_id}_{int(time.time())}.{ext}"
        filepath = os.path.join(AVATARS_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
            
        return f"/uploads/avatars/{filename}"
        
    @staticmethod
    async def uploadBanner(user_id: int, image_bytes: bytes, ext: str = 'jpg') -> str:
        """Saves banner to disk and returns the relative URL path."""
        filename = f"{user_id}_{int(time.time())}_banner.{ext}"
        filepath = os.path.join(BANNERS_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
            
        return f"/uploads/banners/{filename}"

    @staticmethod
    async def deleteAvatar(url: str):
        """Deletes an avatar given its URL path."""
        if not url or not url.startswith("/uploads/avatars/"): return
        filename = url.split('/')[-1]
        filepath = os.path.join(AVATARS_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"[StorageService] Error deleting avatar {filepath}: {e}")

    @staticmethod
    async def deleteBanner(url: str):
        """Deletes a banner given its URL path."""
        if not url or not url.startswith("/uploads/banners/"): return
        filename = url.split('/')[-1]
        filepath = os.path.join(BANNERS_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"[StorageService] Error deleting banner {filepath}: {e}")
