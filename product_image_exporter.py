"""
Fetch all product images from Shopify.
Saves product data including: id, title, handle, and all images with URLs and metadata.
"""

import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
import requests

# Load environment variables
# Look for .env file in project root (3 levels up from this script)
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent
env_file = project_root / '.env'

if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"Loaded .env from: {env_file}")
else:
    # Fallback to default location
    load_dotenv()
    print("Loaded .env from default location")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"fetch_product_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Shopify configuration
SHOP_NAME = os.getenv('SHOPIFY_SHOP_NAME')
ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')

# Try alternative env var names (some scripts use SHOPIFY_API_PASSWORD)
if not ACCESS_TOKEN:
    ACCESS_TOKEN = os.getenv('SHOPIFY_API_PASSWORD')

if not SHOP_NAME or not ACCESS_TOKEN:
    logger.error(f"SHOPIFY_SHOP_NAME: {'Found' if SHOP_NAME else 'Missing'}")
    logger.error(f"SHOPIFY_ACCESS_TOKEN: {'Found' if os.getenv('SHOPIFY_ACCESS_TOKEN') else 'Missing'}")
    logger.error(f"SHOPIFY_API_PASSWORD: {'Found' if os.getenv('SHOPIFY_API_PASSWORD') else 'Missing'}")
    raise ValueError("SHOPIFY_SHOP_NAME and SHOPIFY_ACCESS_TOKEN (or SHOPIFY_API_PASSWORD) must be set in .env file")

# Handle shop name that might already include .myshopify.com
if SHOP_NAME.endswith('.myshopify.com'):
    shop_domain = SHOP_NAME
else:
    shop_domain = f"{SHOP_NAME}.myshopify.com"

BASE_URL = f"https://{shop_domain}/admin/api/2024-01"
HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}

def make_graphql_request(query: str, variables: Dict = None) -> Dict:
    """Make a GraphQL request to Shopify."""
    url = f"https://{shop_domain}/admin/api/2024-01/graphql.json"
    
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {"errors": [{"message": str(e)}]}

def fetch_all_products_with_images() -> List[Dict]:
    """Fetch all products with their images using GraphQL."""
    all_products = []
    cursor = None
    has_next_page = True
    page_count = 0
    
    logger.info("Fetching all products with images from Shopify...")
    logger.info(f"Shop: {shop_domain}")
    logger.info("")
    
    while has_next_page:
        page_count += 1
        
        query = """
        query getProducts($first: Int!, $after: String) {
            products(first: $first, after: $after) {
                edges {
                    node {
                        id
                        title
                        handle
                        images(first: 250) {
                            edges {
                                node {
                                    id
                                    url
                                    altText
                                    width
                                    height
                                }
                            }
                        }
                    }
                    cursor
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        variables = {
            "first": 250,  # Maximum allowed by Shopify
            "after": cursor
        }
        
        response = make_graphql_request(query, variables)
        
        if 'errors' in response:
            logger.error(f"Error fetching products: {response['errors']}")
            break
        
        if 'data' not in response or not response['data']['products']:
            break
        
        edges = response['data']['products']['edges']
        
        for edge in edges:
            node = edge['node']
            
            # Extract numeric ID from GID
            product_gid = node.get('id', '')
            product_id = product_gid.replace('gid://shopify/Product/', '') if product_gid else ''
            
            # Get product title and handle
            product_title = node.get('title', '')
            product_handle = node.get('handle', '')
            
            # Extract images
            images = []
            image_edges = node.get('images', {}).get('edges', [])
            for img_edge in image_edges:
                img_node = img_edge['node']
                image_gid = img_node.get('id', '')
                image_id = image_gid.replace('gid://shopify/ProductImage/', '') if image_gid else ''
                
                images.append({
                    "id": image_id,
                    "gid": image_gid,
                    "url": img_node.get('url', ''),
                    "alt_text": img_node.get('altText', ''),
                    "width": img_node.get('width'),
                    "height": img_node.get('height'),
                    "product_id": product_id,
                    "product_title": product_title,
                    "product_handle": product_handle
                })
            
            product_data = {
                "id": product_id,
                "gid": product_gid,
                "title": product_title,
                "handle": product_handle,
                "image_count": len(images),
                "images": images
            }
            
            all_products.append(product_data)
        
        logger.info(f"Page {page_count}: Fetched {len(edges)} products (Total: {len(all_products)})")
        
        page_info = response['data']['products']['pageInfo']
        has_next_page = page_info['hasNextPage']
        cursor = page_info['endCursor']
        
        # Rate limiting - Shopify allows 2 requests per second
        if has_next_page:
            time.sleep(0.5)
    
    logger.info("")
    logger.info(f"Total products fetched: {len(all_products)}")
    
    # Calculate total images
    total_images = sum(len(p['images']) for p in all_products)
    logger.info(f"Total images: {total_images}")
    
    return all_products

def save_products_to_json(products: List[Dict], filename: str = None) -> str:
    """Save products data to JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"all_products_images_{timestamp}.json"
    
    output_data = {
        "metadata": {
            "shop": SHOP_NAME,
            "generated_at": datetime.now().isoformat(),
            "total_products": len(products),
            "total_images": sum(len(p['images']) for p in products)
        },
        "products": products
    }
    
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(products)} products to: {filepath}")
    return filepath

def main():
    """Main function."""
    try:
        # Fetch all products with images
        products = fetch_all_products_with_images()
        
        if not products:
            logger.warning("No products found!")
            return
        
        # Save to JSON
        output_file = save_products_to_json(products)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total products: {len(products)}")
        logger.info(f"Total images: {sum(len(p['images']) for p in products)}")
        logger.info(f"Output file: {output_file}")
        logger.info("=" * 80)
        
        # Show some statistics
        products_with_images = [p for p in products if p['image_count'] > 0]
        products_without_images = [p for p in products if p['image_count'] == 0]
        
        logger.info(f"Products with images: {len(products_with_images)}")
        logger.info(f"Products without images: {len(products_without_images)}")
        
        if products_without_images:
            logger.warning(f"\nProducts without images ({len(products_without_images)}):")
            for p in products_without_images[:10]:  # Show first 10
                logger.warning(f"  - {p['title']} (ID: {p['id']}, Handle: {p['handle']})")
            if len(products_without_images) > 10:
                logger.warning(f"  ... and {len(products_without_images) - 10} more")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()

