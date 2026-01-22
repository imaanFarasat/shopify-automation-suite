import os
import json
import time
import logging
import sys
from typing import Dict, List, Optional, Tuple
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging with visual formatting
def setup_logging():
    """Setup visual logging with fresh log file"""
    # Remove existing log file to start fresh
    if os.path.exists('shopify_metadata_updater.log'):
        os.remove('shopify_metadata_updater.log')
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')
    
    # Setup file handler
    file_handler = logging.FileHandler('shopify_metadata_updater.log', mode='w')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Setup console handler with visual formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Fix Unicode encoding for Windows console
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Setup logging
logger = setup_logging()
logger = logging.getLogger(__name__)

class ShopifyMetadataUpdater:
    def __init__(self):
        self.shop_name = os.getenv('SHOPIFY_SHOP_NAME')
        self.api_key = os.getenv('SHOPIFY_API_KEY')
        self.api_password = os.getenv('SHOPIFY_API_PASSWORD')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        if not all([self.shop_name, self.api_key, self.api_password, self.gemini_api_key]):
            raise ValueError("Missing required environment variables")
        
        # Handle shop name that might already include .myshopify.com
        if self.shop_name.endswith('.myshopify.com'):
            shop_domain = self.shop_name
        else:
            shop_domain = f"{self.shop_name}.myshopify.com"
        
        self.base_url = f"https://{shop_domain}/admin/api/2024-01"
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_password
        }
        
        # Configure Gemini
        genai.configure(api_key=self.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Set default vendor
        self.default_vendor = "RezaGemCollection"
        
        logger.info("="*60)
        logger.info("SHOPIFY METADATA UPDATER STARTED")
        logger.info("="*60)
        logger.info(f"Shop: {self.shop_name}")
        logger.info(f"AI Model: gemini-2.0-flash")
        logger.info(f"Default Vendor: {self.default_vendor}")
        logger.info("")

    def _make_graphql_request(self, query: str, variables: Dict = None) -> Dict:
        """Make a GraphQL request to Shopify"""
        url = f"{self.base_url}/graphql.json"
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        try:
            # Add SSL verification and timeout settings
            response = requests.post(
                url, 
                headers=self.headers, 
                json=payload, 
                timeout=30,
                verify=True  # Ensure SSL verification
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error: {e}")
            logger.error("Try updating your certificates or check your network connection")
            return {"errors": [{"message": f"SSL Error: {e}"}]}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"errors": [{"message": str(e)}]}

    def check_collection_metadata(self, collection_id: str) -> Dict:
        """Check if collection has existing meta title and description"""
        query = """
        query getCollection($id: ID!) {
            collection(id: $id) {
                id
                title
                seo {
                    title
                    description
                }
            }
        }
        """
        
        variables = {"id": f"gid://shopify/Collection/{collection_id}"}
        
        response = self._make_graphql_request(query, variables)
        
        if 'errors' in response:
            logger.error(f"Error fetching collection metadata: {response['errors']}")
            return None
            
        collection = response['data']['collection']
        if not collection:
            logger.error(f"Collection {collection_id} not found")
            return None
            
        seo = collection.get('seo', {})
        has_title = bool(seo.get('title'))
        has_description = bool(seo.get('description'))
        
        logger.info("="*50)
        logger.info(f"COLLECTION: {collection['title']}")
        logger.info("="*50)
        logger.info(f"Meta Title: {'YES' if has_title else 'NO'}")
        logger.info(f"Meta Description: {'YES' if has_description else 'NO'}")
        logger.info("")
        
        return {
            'id': collection['id'],
            'title': collection['title'],
            'has_meta_title': has_title,
            'has_meta_description': has_description,
            'current_seo': seo
        }

    def get_collection_products_missing_meta(self, collection_id: str, limit: int = 20) -> List[Dict]:
        """Fetch products from collection that are missing meta title or description"""
        products = []
        cursor = None
        has_next_page = True
        
        logger.info(f"Searching for products missing metadata in collection {collection_id}...")
        
        while has_next_page and len(products) < limit:
            query = """
            query getCollectionProducts($id: ID!, $first: Int!, $after: String) {
                collection(id: $id) {
                    products(first: $first, after: $after) {
                        edges {
                            node {
                                id
                                title
                                handle
                                seo {
                                    title
                                    description
                                }
                                description
                                tags
                                productType
                                vendor
                            }
                            cursor
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
            """
            
            variables = {
                "id": f"gid://shopify/Collection/{collection_id}",
                "first": 50,
                "after": cursor
            }
            
            response = self._make_graphql_request(query, variables)
            
            if 'errors' in response:
                logger.error(f"Error fetching products: {response['errors']}")
                break
                
            collection = response['data']['collection']
            if not collection:
                logger.error(f"Collection {collection_id} not found")
                break
                
            edges = collection['products']['edges']
            for edge in edges:
                product = edge['node']
                seo = product.get('seo', {})
                
                # Check if product is missing meta title or description
                title = seo.get('title') or ''
                description = seo.get('description') or ''
                has_title = bool(title and title.strip())
                has_description = bool(description and description.strip())
                
                # Only include products missing metadata
                if not has_title or not has_description:
                    products.append(product)
                    logger.info(f"  Found missing metadata: {product['title']}")
                    
                    if len(products) >= limit:
                        break
                
            page_info = collection['products']['pageInfo']
            has_next_page = page_info['hasNextPage']
            cursor = page_info['endCursor']
            
            # Rate limiting
            time.sleep(0.5)
        
        logger.info(f"Found {len(products)} products missing metadata (limit: {limit})")
        return products

    def validate_metadata_quality(self, title: str, description: str) -> Tuple[bool, str]:
        """Validate metadata quality and return issues found"""
        issues = []
        
        if not title:
            issues.append("Missing title")
        elif len(title) < 50:
            issues.append(f"Title too short ({len(title)} chars, needs 50+)")
        elif len(title) > 60:
            issues.append(f"Title too long ({len(title)} chars, needs 60 max)")
            
        if not description:
            issues.append("Missing description")
        elif len(description) < 150:
            issues.append(f"Description too short ({len(description)} chars, needs 150+)")
        elif len(description) > 160:
            issues.append(f"Description too long ({len(description)} chars, needs 160 max)")
        elif description and not description[-1] in '.!?':
            issues.append("Description doesn't end with proper punctuation")
            
        return len(issues) == 0, "; ".join(issues)

    def generate_metadata_with_gemini(self, product: Dict) -> Tuple[str, str]:
        """Generate SEO title and meta description using Gemini AI"""
        prompt = f"""
        Generate SEO-optimized metadata for this Shopify product:
        
        Product Title: {product['title']}
        Product Type: {product.get('productType', 'N/A')}
        Vendor: {product.get('vendor', self.default_vendor)}
        Tags: {', '.join(product.get('tags', []))}
        Description: {product.get('description', 'N/A')[:500]}...
        
        Requirements:
        1. Title tag: 50-60 characters, compelling and keyword-rich
        2. Meta description: 150-160 characters, persuasive and includes call-to-action
        3. CRITICAL: Write ONLY complete sentences that end with proper punctuation (. ! ?)
        4. NEVER cut off words or sentences mid-way
        5. If you cannot fit a complete sentence within 160 characters, write a shorter but complete sentence
        6. Ensure the description ends with a period, exclamation mark, or question mark
        7. Include "RezaGemCollection" brand name in the content when appropriate
        8. Focus on gemstone beads, jewelry making, and high-quality gemstone keywords
        
        Return ONLY a JSON object with this exact format:
        {{"title": "your title here", "description": "your description here"}}
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Extract JSON from response
            if '```json' in result_text:
                json_start = result_text.find('```json') + 8
                json_end = result_text.find('```', json_start)
                result_text = result_text[json_start:json_end].strip()
            elif '```' in result_text:
                json_start = result_text.find('```') + 3
                json_end = result_text.find('```', json_start)
                result_text = result_text[json_start:json_end].strip()
            
            metadata = json.loads(result_text)
            
            # Validate character limits and ensure complete sentences
            title = metadata['title'][:60]  # Ensure max 60 chars
            
            # For description, ensure it's a complete sentence within 160 chars
            description = metadata['description']
            if len(description) > 160:
                # Find the last complete sentence within 160 characters
                truncated = description[:160]
                last_period = truncated.rfind('.')
                last_exclamation = truncated.rfind('!')
                last_question = truncated.rfind('?')
                
                # Use the last complete sentence ending
                last_sentence_end = max(last_period, last_exclamation, last_question)
                if last_sentence_end > 100:  # Only if we have a reasonable length
                    description = description[:last_sentence_end + 1]
                else:
                    # If no good sentence break found, try to find a word boundary
                    last_space = truncated.rfind(' ')
                    if last_space > 80:  # Ensure reasonable length
                        description = description[:last_space] + "..."
                    else:
                        description = description[:160]  # Fallback to hard cut
            else:
                # Ensure description ends with proper punctuation
                if description and not description[-1] in '.!?':
                    description = description.rstrip() + '.'
            
            # Validate the generated metadata
            is_valid, issues = self.validate_metadata_quality(title, description)
            if not is_valid:
                logger.warning(f"  Generated metadata has issues: {issues}")
            
            logger.info(f"  Generated metadata:")
            logger.info(f"     Title ({len(title)} chars): {title}")
            logger.info(f"     Description ({len(description)} chars): {description}")
            
            return title, description
            
        except Exception as e:
            logger.error(f"Error generating metadata with Gemini: {e}")
            logger.info("Using fallback metadata generation...")
            
            # Enhanced fallback metadata
            product_title = product['title']
            vendor = product.get('vendor', 'Shop')
            product_type = product.get('productType', '')
            
            # Create SEO-friendly title
            if product_type:
                title = f"{product_title} | {product_type} | {vendor}"
            else:
                title = f"{product_title} | {vendor}"
            
            # Create SEO-friendly description
            description = f"Shop {product_title} online. "
            if product_type:
                description += f"Premium {product_type.lower()} "
            description += f"from {vendor}. "
            if product.get('description'):
                desc_snippet = product['description'][:80].replace('\n', ' ').strip()
                description += desc_snippet
            description += " Order now!"
            
            # Ensure character limits and complete sentences
            title = title[:60]
            
            # For description, ensure it's a complete sentence within 160 chars
            if len(description) > 160:
                # Find the last complete sentence within 160 characters
                truncated = description[:160]
                last_period = truncated.rfind('.')
                last_exclamation = truncated.rfind('!')
                last_question = truncated.rfind('?')
                
                # Use the last complete sentence ending
                last_sentence_end = max(last_period, last_exclamation, last_question)
                if last_sentence_end > 100:  # Only if we have a reasonable length
                    description = description[:last_sentence_end + 1]
                else:
                    # If no good sentence break found, try to find a word boundary
                    last_space = truncated.rfind(' ')
                    if last_space > 80:  # Ensure reasonable length
                        description = description[:last_space] + "..."
                    else:
                        description = description[:160]  # Fallback to hard cut
            else:
                # Ensure description ends with proper punctuation
                if description and not description[-1] in '.!?':
                    description = description.rstrip() + '.'
            
            # Validate the fallback metadata
            is_valid, issues = self.validate_metadata_quality(title, description)
            if not is_valid:
                logger.warning(f"  Fallback metadata has issues: {issues}")
            
            logger.info(f"  Fallback metadata:")
            logger.info(f"     Title ({len(title)} chars): {title}")
            logger.info(f"     Description ({len(description)} chars): {description}")
            
            return title, description

    def update_product_metadata(self, product_id: str, title: str, description: str) -> bool:
        """Update product SEO metadata using GraphQL"""
        mutation = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                    seo {
                        title
                        description
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": product_id,
                "seo": {
                    "title": title,
                    "description": description
                }
            }
        }
        
        response = self._make_graphql_request(mutation, variables)
        
        if 'errors' in response:
            logger.error(f"GraphQL errors: {response['errors']}")
            return False
            
        result = response['data']['productUpdate']
        if result['userErrors']:
            logger.error(f"Product update errors: {result['userErrors']}")
            return False
            
        logger.info(f"  SUCCESS - Product updated")
        return True

    def generate_collection_metadata(self, collection: Dict) -> Tuple[str, str]:
        """Generate SEO metadata for collection using Gemini AI"""
        prompt = f"""
        Generate SEO-optimized metadata for this Shopify collection:
        
        Collection Title: {collection['title']}
        Collection Handle: {collection.get('handle', 'N/A')}
        Description: {collection.get('description', 'N/A')[:500]}...
        
        Requirements:
        1. Title tag: 50-60 characters, compelling and keyword-rich
        2. Meta description: 150-160 characters, persuasive and includes call-to-action
        3. CRITICAL: Write ONLY complete sentences that end with proper punctuation (. ! ?)
        4. NEVER cut off words or sentences mid-way
        5. If you cannot fit a complete sentence within 160 characters, write a shorter but complete sentence
        6. Ensure the description ends with a period, exclamation mark, or question mark
        7. Focus on gemstone beads, jewelry making, and collection-specific keywords
        8. Include "RezaGemCollection" brand name in the content when appropriate
        9. Emphasize high-quality, handpicked gemstones and jewelry making supplies
        
        Return ONLY a JSON object with this exact format:
        {{"title": "your title here", "description": "your description here"}}
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Extract JSON from response
            if '```json' in result_text:
                json_start = result_text.find('```json') + 8
                json_end = result_text.find('```', json_start)
                result_text = result_text[json_start:json_end].strip()
            elif '```' in result_text:
                json_start = result_text.find('```') + 3
                json_end = result_text.find('```', json_start)
                result_text = result_text[json_start:json_end].strip()
            
            metadata = json.loads(result_text)
            
            # Validate character limits and ensure complete sentences
            title = metadata['title'][:60]  # Ensure max 60 chars
            
            # For description, ensure it's a complete sentence within 160 chars
            description = metadata['description']
            if len(description) > 160:
                # Find the last complete sentence within 160 characters
                truncated = description[:160]
                last_period = truncated.rfind('.')
                last_exclamation = truncated.rfind('!')
                last_question = truncated.rfind('?')
                
                # Use the last complete sentence ending
                last_sentence_end = max(last_period, last_exclamation, last_question)
                if last_sentence_end > 100:  # Only if we have a reasonable length
                    description = description[:last_sentence_end + 1]
                else:
                    # If no good sentence break found, try to find a word boundary
                    last_space = truncated.rfind(' ')
                    if last_space > 80:  # Ensure reasonable length
                        description = description[:last_space] + "..."
                    else:
                        description = description[:160]  # Fallback to hard cut
            else:
                # Ensure description ends with proper punctuation
                if description and not description[-1] in '.!?':
                    description = description.rstrip() + '.'
            
            logger.info(f"  Generated collection metadata:")
            logger.info(f"     Title ({len(title)} chars): {title}")
            logger.info(f"     Description ({len(description)} chars): {description}")
            
            return title, description
            
        except Exception as e:
            logger.error(f"Error generating collection metadata with Gemini: {e}")
            logger.info("Using fallback collection metadata generation...")
            
            # Enhanced fallback metadata
            collection_title = collection['title']
            
            # Create SEO-friendly title
            title = f"{collection_title} | Gemstone Beads | Reza Gem Collection"
            title = title[:60]  # Ensure max 60 chars
            
            # Create SEO-friendly description
            description = f"Shop {collection_title} online. "
            if 'bead' in collection_title.lower():
                description += f"Premium gemstone beads for jewelry making. "
            description += f"High-quality stones from Reza Gem Collection. "
            if collection.get('description'):
                desc_snippet = collection['description'][:80].replace('\n', ' ').strip()
                description += desc_snippet
            description += " Order now!"
            
            # Ensure character limits and complete sentences
            if len(description) > 160:
                truncated = description[:160]
                last_period = truncated.rfind('.')
                last_exclamation = truncated.rfind('!')
                last_question = truncated.rfind('?')
                
                last_sentence_end = max(last_period, last_exclamation, last_question)
                if last_sentence_end > 100:
                    description = description[:last_sentence_end + 1]
                else:
                    last_space = truncated.rfind(' ')
                    if last_space > 80:
                        description = description[:last_space] + "..."
                    else:
                        description = description[:160]
            else:
                if description and not description[-1] in '.!?':
                    description = description.rstrip() + '.'
            
            logger.info(f"  Fallback collection metadata:")
            logger.info(f"     Title ({len(title)} chars): {title}")
            logger.info(f"     Description ({len(description)} chars): {description}")
            
            return title, description

    def update_collection_metadata(self, collection_id: str, title: str, description: str) -> bool:
        """Update collection SEO metadata using GraphQL"""
        mutation = """
        mutation collectionUpdate($input: CollectionInput!) {
            collectionUpdate(input: $input) {
                collection {
                    id
                    seo {
                        title
                        description
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": collection_id,
                "seo": {
                    "title": title,
                    "description": description
                }
            }
        }
        
        response = self._make_graphql_request(mutation, variables)
        
        if 'errors' in response:
            logger.error(f"GraphQL errors: {response['errors']}")
            return False
            
        result = response['data']['collectionUpdate']
        if result['userErrors']:
            logger.error(f"Collection update errors: {result['userErrors']}")
            return False
            
        logger.info(f"  SUCCESS - Collection SEO updated")
        return True

    def process_collection(self, collection_id: str, limit: int = 20):
        """Main method to process a collection and update metadata"""
        logger.info(f"Starting metadata update for collection {collection_id}")
        logger.info(f"Product limit: {limit}")
        
        # Check collection metadata
        collection_info = self.check_collection_metadata(collection_id)
        if not collection_info:
            logger.error(f"Could not fetch collection {collection_id}")
            return
        
        # Update collection metadata if missing
        if not collection_info['has_meta_title'] or not collection_info['has_meta_description']:
            logger.info("="*50)
            logger.info("UPDATING COLLECTION METADATA")
            logger.info("="*50)
            
            # Generate collection metadata
            collection_title, collection_description = self.generate_collection_metadata(collection_info)
            
            # Update collection
            if self.update_collection_metadata(collection_info['id'], collection_title, collection_description):
                logger.info(f"✓ Collection metadata updated successfully")
            else:
                logger.error(f"✗ Failed to update collection metadata")
        else:
            logger.info("Collection already has metadata - skipping collection update")
        
        # Get products missing metadata
        products = self.get_collection_products_missing_meta(collection_id, limit)
        if not products:
            logger.info("No products found missing metadata in this collection!")
            return
            
        logger.info("="*50)
        logger.info(f"UPDATING {len(products)} PRODUCTS MISSING METADATA")
        logger.info("="*50)
        logger.info("")
        
        # Process each product
        updated_count = 0
        failed_count = 0
        
        for i, product in enumerate(products, 1):
            logger.info(f"[{i}/{len(products)}] {product['title']}")
            
            # Check what's missing
            seo = product.get('seo', {})
            current_title = seo.get('title') or ''
            current_description = seo.get('description') or ''
            
            missing_parts = []
            if not current_title.strip():
                missing_parts.append("title")
            if not current_description.strip():
                missing_parts.append("description")
            
            logger.info(f"  Missing: {', '.join(missing_parts)}")
            
            # Generate new metadata
            title, description = self.generate_metadata_with_gemini(product)
            
            # Update product
            if self.update_product_metadata(product['id'], title, description):
                updated_count += 1
                logger.info(f"  COMPLETED - {product['title']}")
            else:
                failed_count += 1
                logger.error(f"  FAILED - {product['title']}")
            
            # Rate limiting
            time.sleep(1)
        
        logger.info("")
        logger.info("="*60)
        logger.info("FINAL RESULTS")
        logger.info("="*60)
        logger.info(f"Updated: {updated_count} products")
        logger.info(f"Failed: {failed_count} products")
        logger.info(f"Total: {len(products)} products processed")
        logger.info("")
        logger.info("METADATA UPDATE COMPLETE!")
        logger.info("Check shopify_metadata_updater.log for detailed results")

def main():
    """Main execution function"""
    try:
        updater = ShopifyMetadataUpdater()
        
        # Collection ID from command line or default
        collection_id = "286924505178"  # Default collection ID
        limit = 20  # Default limit
        
        if len(sys.argv) > 1:
            collection_id = sys.argv[1]
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[2])
            except ValueError:
                logger.warning(f"Invalid limit value '{sys.argv[2]}', using default 20")
        
        logger.info(f"Processing collection: {collection_id}")
        logger.info(f"Product limit: {limit}")
        logger.info("")
        
        updater.process_collection(collection_id, limit)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
