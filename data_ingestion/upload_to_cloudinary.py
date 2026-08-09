import os
import time
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Configure Cloudinary
cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET") 
)

VISUALS_DIR = r"C:\Users\P\Documents\finnai\data\nifty_top20\visuals"

def get_all_images(base_dir):
    image_paths = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                full_path = os.path.join(root, file)
                # Compute relative path like HDFCBANK/FY2025/table1.png
                rel_path = os.path.relpath(full_path, base_dir)
                image_paths.append((full_path, rel_path))
    return image_paths

def upload_images():
    print("Gathering local images...")
    images = get_all_images(VISUALS_DIR)
    print(f"Found {len(images)} images to upload.")

    success_count = 0
    fail_count = 0

    for i, (full_path, rel_path) in enumerate(images):
        # Create a clean public_id (no file extension, forward slashes)
        public_id = "finnai/visuals/" + os.path.splitext(rel_path.replace("\\", "/"))[0]
        
        print(f"[{i+1}/{len(images)}] Uploading {rel_path}...", end=" ", flush=True)
        
        try:
            # We set overwrite=True to allow restarting if interrupted
            response = cloudinary.uploader.upload(
                full_path, 
                public_id=public_id,
                unique_filename=False,
                overwrite=True
            )
            print("OK!")
            success_count += 1
            # Rate limiting buffer
            time.sleep(0.1) 
        except Exception as e:
            print(f"FAILED! Error: {e}")
            fail_count += 1

    print(f"\n--- Upload Complete ---")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    upload_images()

