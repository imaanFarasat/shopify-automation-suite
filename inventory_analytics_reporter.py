"""Fetch products from collection with variants having inventory 1 or 2"""
import json
import os
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

shop_name = os.getenv('SHOPIFY_SHOP_NAME')
api_password = os.getenv('SHOPIFY_API_PASSWORD')

if not all([shop_name, api_password]):
    raise ValueError("Missing required environment variables: SHOPIFY_SHOP_NAME or SHOPIFY_API_PASSWORD")

if shop_name.endswith('.myshopify.com'):
    shop_domain = shop_name
else:
    shop_domain = f"{shop_name}.myshopify.com"

base_url = f"https://{shop_domain}/admin/api/2024-10"
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Shopify-Access-Token': api_password
}

COLLECTION_ID = "286924505178"
OUTPUT_FILE = "low-inventory-products.json"

def make_graphql_request(query: str, variables: dict = None) -> dict:
    """Make a GraphQL request to Shopify"""
    url = f"{base_url}/graphql.json"
    payload = {
        "query": query,
        "variables": variables or {}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Error details: {error_detail}")
            except:
                print(f"Response text: {e.response.text}")
        return {"errors": [{"message": str(e)}]}

def get_collection_products_with_low_inventory(collection_id: str) -> List[Dict]:
    """Get all products from collection with variants having inventory 1 or 2"""
    all_products = []
    cursor = None
    has_next_page = True
    page = 1
    
    print(f"Fetching products from collection {collection_id}...")
    print()
    
    query = """
    query getCollectionProducts($collectionId: ID!, $cursor: String) {
      collection(id: $collectionId) {
        id
        title
        handle
        products(first: 50, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              id
              title
              handle
              featuredImage {
                id
                url
                altText
              }
              variants(first: 250) {
                edges {
                  node {
                    id
                    title
                    price
                    sku
                    inventoryQuantity
                    selectedOptions {
                      name
                      value
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    while has_next_page:
        print(f"Fetching page {page}...")
        
        gid = f"gid://shopify/Collection/{collection_id}"
        variables = {
            "collectionId": gid,
            "cursor": cursor
        }
        
        response = make_graphql_request(query, variables)
        
        if 'errors' in response:
            print(f"Error fetching products: {response['errors']}")
            break
        
        data = response.get('data', {})
        collection = data.get('collection')
        
        if not collection:
            print("Collection not found")
            break
        
        products = collection.get('products', {})
        edges = products.get('edges', [])
        
        for edge in edges:
            node = edge['node']
            product_id = node['id'].split('/')[-1]
            
            # Get main image
            featured_image = node.get('featuredImage')
            main_image = None
            if featured_image:
                main_image = {
                    "url": featured_image.get('url', ''),
                    "alt_text": featured_image.get('altText', '')
                }
            
            # Filter variants with inventory 1 or 2
            low_inventory_variants = []
            variants = node.get('variants', {}).get('edges', [])
            
            for variant_edge in variants:
                variant_node = variant_edge['node']
                inventory_qty = variant_node.get('inventoryQuantity', 0)
                
                if inventory_qty in [1, 2]:
                    variant_id = variant_node['id'].split('/')[-1]
                    selected_options = variant_node.get('selectedOptions', [])
                    
                    low_inventory_variants.append({
                        "variant_id": variant_id,
                        "title": variant_node.get('title', ''),
                        "price": variant_node.get('price', ''),
                        "sku": variant_node.get('sku', ''),
                        "inventory_quantity": inventory_qty,
                        "options": {opt['name']: opt['value'] for opt in selected_options}
                    })
            
            # Only add product if it has low inventory variants
            if low_inventory_variants:
                all_products.append({
                    "product_id": product_id,
                    "product_title": node.get('title', ''),
                    "product_handle": node.get('handle', ''),
                    "main_image": main_image,
                    "low_inventory_variants": low_inventory_variants,
                    "total_low_inventory_variants": len(low_inventory_variants)
                })
        
        page_info = products.get('pageInfo', {})
        has_next_page = page_info.get('hasNextPage', False)
        cursor = page_info.get('endCursor')
        page += 1
        time.sleep(0.5)  # Rate limiting
    
    return all_products

def main():
    print("=" * 60)
    print("FETCHING LOW INVENTORY PRODUCTS")
    print("=" * 60)
    print()
    
    products = get_collection_products_with_low_inventory(COLLECTION_ID)
    
    # Calculate totals
    total_products = len(products)
    total_variants = sum(p['total_low_inventory_variants'] for p in products)
    qty_1_count = sum(1 for p in products for v in p['low_inventory_variants'] if v['inventory_quantity'] == 1)
    qty_2_count = sum(1 for p in products for v in p['low_inventory_variants'] if v['inventory_quantity'] == 2)
    
    # Create output structure
    output_data = {
        "collection_id": COLLECTION_ID,
        "export_date": datetime.now().isoformat(),
        "inventory_threshold": "1 or 2",
        "summary": {
            "total_products_with_low_inventory": total_products,
            "total_low_inventory_variants": total_variants,
            "variants_with_quantity_1": qty_1_count,
            "variants_with_quantity_2": qty_2_count
        },
        "products": products
    }
    
    # Save to JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total products with low inventory: {total_products}")
    print(f"Total low inventory variants: {total_variants}")
    print(f"  - Variants with quantity 1: {qty_1_count}")
    print(f"  - Variants with quantity 2: {qty_2_count}")
    print()
    print(f"Results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
