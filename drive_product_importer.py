import json
import os
import base64
import time
import io
import requests
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

"""
Drive Product Importer & Sync Manager
-------------------------------------
This script automates the creation of Shopify products from a local JSON dataset (exported from Excel/Sheets),
synchronizing product images directly from Google Drive.

Key Features:
- Reads product data from JSON.
- Groups rows into single products with multiple variants (e.g., Color groupings).
- Fetches high-res images from a specified Google Drive folder map.
- Creates products, variants, and metafields via Shopify Admin API.
- Assigns products to collections automatically.
"""

# Load environment variables
load_dotenv()

# --- Configuration ---
# Update these paths for your environment
JSON_VIDEOS_PATH = "product_data_source.json" 
DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID", "YOUR_DRIVE_FOLDER_ID")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# --- Google Drive Helpers ---

def get_drive_service():
    """Builds an authenticated Google Drive API service."""
    creds: Optional[Credentials] = None
    token_path = "token.json"
    credentials_path = "credentials.json"

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"credentials.json not found. Please add your OAuth client file.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)

def find_images_in_drive(folder_name: str, drive_service) -> List[Tuple[bytes, str]]:
    """
    Finds a folder by name inside DRIVE_ROOT_FOLDER_ID, then downloads all images in it.
    Returns a list of (image_bytes, filename).
    """
    if not folder_name:
        return []

    # 1. Find the subfolder
    query = (
        f"'{DRIVE_ROOT_FOLDER_ID}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{folder_name}' and trashed = false"
    )
    resp = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = resp.get('files', [])
    
    if not folders:
        print(f"Warning: Drive folder '{folder_name}' not found.")
        return []
    
    folder_id = folders[0]['id']

    # 2. List images in subfolder
    img_query = (
        f"'{folder_id}' in parents and "
        f"mimeType contains 'image/' and trashed = false"
    )
    img_resp = drive_service.files().list(
        q=img_query, spaces='drive', fields='files(id, name)', orderBy='name'
    ).execute()
    
    files = img_resp.get('files', [])
    results = []
    
    print(f"  Found {len(files)} images in folder '{folder_name}'...")
    
    for f in files:
        file_id = f['id']
        filename = f.get('name', 'image.jpg')
        
        # Download
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        results.append((fh.getvalue(), filename))
        
    return results

# --- Shopify Helpers ---

def get_shopify_headers():
    shop_name = os.getenv("SHOPIFY_SHOP_NAME")
    token = os.getenv("SHOPIFY_ACCESS_TOKEN") 
    
    if not token:
        # Fallback for legacy setups
        token = os.getenv("SHOPIFY_API_PASSWORD")
        
    if not shop_name or not token:
        raise ValueError("Missing SHOPIFY_SHOP_NAME or SHOPIFY_ACCESS_TOKEN in .env")

    if not shop_name.endswith(".myshopify.com"):
        shop_domain = f"{shop_name}.myshopify.com"
    else:
        shop_domain = shop_name

    base_url = f"https://{shop_domain}/admin/api/2024-01"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token
    }
    return base_url, headers

def create_product(base_url, headers, payload):
    url = f"{base_url}/products.json"
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 201:
        data = resp.json()
        print(f"  Success! Product ID: {data['product']['id']}")
        return data
    else:
        print(f"  Error creating product: {resp.status_code}")
        print(resp.text)
        return None

def add_to_collection(base_url, headers, product_id, collection_id):
    url = f"{base_url}/collects.json"
    payload = {
        "collect": {
            "product_id": product_id,
            "collection_id": collection_id
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 201:
        print(f"    -> Added to collection {collection_id}")
    else:
        print(f"    -> Failed to add to collection {collection_id}: {resp.status_code} {resp.text}")

# --- Main Logic ---

def clean_value(val):
    if val is None:
        return ""
    return str(val).strip()

def process_product_import():
    """
    Main execution function.
    Reads JSON data, groups by product, and uploads to Shopify with Images from Drive.
    """
    if not os.path.exists(JSON_VIDEOS_PATH):
        print(f"Data source {JSON_VIDEOS_PATH} not found. Please export your Excel to JSON.")
        return

    print(f"Reading {JSON_VIDEOS_PATH}...")
    with open(JSON_VIDEOS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    drive_service = get_drive_service()
    base_url, headers = get_shopify_headers()

    # Group rows into products
    # Logic: A new product starts when "Gemstone Name" (or primary grouping key) is present.
    products_to_create = []
    current_product_group = []
    
    for row in data:
        # Check if this row initiates a new product
        is_new_product = bool(row.get("Gemstone Name", "").strip())
        
        if is_new_product:
            if current_product_group:
                products_to_create.append(current_product_group)
            current_product_group = [row]
        else:
            if not current_product_group:
                current_product_group = [row]
            else:
                current_product_group.append(row)
    
    if current_product_group:
        products_to_create.append(current_product_group)

    print(f"Found {len(products_to_create)} products to create.")

    for i, group in enumerate(products_to_create, 1):
        first_row = group[0]
        title = first_row.get("Title", "Untitled Product")
        
        print(f"\n[{i}/{len(products_to_create)}] Preparing: {title}")
        
        # --- Metafields (Custom Definitions) ---
        def collect_joined_metafield(rows, key):
            values = [clean_value(r.get(key)) for r in rows]
            non_empty_values = [v for v in values if v]
            return ", ".join(non_empty_values)

        length_val = collect_joined_metafield(group, "Length")
        width_val = collect_joined_metafield(group, "Width")
        pin_val = collect_joined_metafield(group, "Pin Thickness")
        
        metafields = []
        if length_val:
            metafields.append({"namespace": "custom", "key": "length", "value": length_val, "type": "single_line_text_field"})
        if width_val:
            metafields.append({"namespace": "custom", "key": "width", "value": width_val, "type": "single_line_text_field"})

        # --- Variants ---
        variants = []
        options = []
        
        has_color_option = False
        colors = [clean_value(r.get("Stone Colour")) for r in group]
        if any(colors):
            has_color_option = True
            options.append({"name": "Stone Colour"})

        for row in group:
            price = clean_value(row.get("Price"))
            quantity = row.get("Quantity", 0)
            try:
                inventory_qty = int(quantity)
            except (ValueError, TypeError):
                inventory_qty = 0
            
            variant_obj = {
                "price": price,
                "inventory_management": "shopify",
                "inventory_quantity": inventory_qty
            }
            
            if has_color_option:
                color_val = clean_value(row.get("Stone Colour")) or "Default"
                variant_obj["option1"] = color_val
            
            variants.append(variant_obj)

        # --- Images from Drive ---
        photo_folder = clean_value(first_row.get("Photo Folder"))
        product_images = []
        
        if photo_folder:
            print(f"  Fetching images from Drive folder: '{photo_folder}'")
            image_files = find_images_in_drive(photo_folder, drive_service)
            
            for img_bytes, img_name in image_files:
                b64_data = base64.b64encode(img_bytes).decode('utf-8')
                product_images.append({
                    "attachment": b64_data,
                    "filename": img_name
                })
        else:
            print("  No Photo Folder specified.")

        # --- Construct Payload ---
        product_payload = {
            "title": title,
            "body_html": f"<strong>Material:</strong> {first_row.get('Material', 'Sterling Silver')}<br>",
            "product_type": "Findings",
            "variants": variants,
            "metafields": metafields,
            "images": product_images
        }
        
        if options:
            product_payload["options"] = options

        # Create
        created_data = create_product(base_url, headers, {"product": product_payload})
        time.sleep(1) # Rate limit politeness

        if created_data and 'product' in created_data:
            product_id = created_data['product']['id']
            
            # --- Assign Collections ---
            main_coll_id = clean_value(first_row.get("Main Collection"))
            if main_coll_id:
                add_to_collection(base_url, headers, product_id, main_coll_id)

if __name__ == "__main__":
    process_product_import()
