import os
import json
import re
import logging
import requests
import time
from typing import Dict, Optional, Tuple, List
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"blog_send_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ShopifyBlogSender:
    def __init__(self):
        self.shop_name = os.getenv('SHOPIFY_SHOP_NAME')
        self.api_password = os.getenv('SHOPIFY_API_PASSWORD')
        
        if not all([self.shop_name, self.api_password]):
            raise ValueError("Missing required environment variables: SHOPIFY_SHOP_NAME or SHOPIFY_API_PASSWORD")
        
        # Handle shop name
        if self.shop_name.endswith('.myshopify.com'):
            shop_domain = self.shop_name
        else:
            shop_domain = f"{self.shop_name}.myshopify.com"
        
        # Use latest API version
        self.base_url = f"https://{shop_domain}/admin/api/2024-10"
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_password
        }
        
        self.results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
        
        logger.info("="*60)
        logger.info("SHOPIFY BLOG SENDER - BATCH MODE")
        logger.info("="*60)
        logger.info(f"Shop: {self.shop_name}")
        logger.info(f"API Version: 2024-10")
        logger.info(f"Log file: {log_filename}")
        logger.info("")
    
    def _make_rest_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make a REST API request to Shopify"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, timeout=30, verify=True)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=30, verify=True)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data, timeout=30, verify=True)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"REST Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    logger.error(f"Response text: {e.response.text}")
            return {"errors": [{"message": str(e)}]}
    
    def get_or_create_blog(self, blog_title: str = "Blog") -> Optional[str]:
        """Get existing blog or create a new one. Returns blog ID."""
        logger.info(f"Checking for blog: {blog_title}")
        
        # Fetch blogs using REST API
        rest_response = self._make_rest_request('GET', 'blogs.json')
        
        if 'errors' in rest_response:
            logger.error(f"Error fetching blogs: {rest_response['errors']}")
            return None
        
        # Check if blog exists
        if 'blogs' in rest_response:
            for blog in rest_response['blogs']:
                if blog['title'].lower() == blog_title.lower():
                    blog_id = blog['id']
                    logger.info(f"Found existing blog: {blog['title']} (ID: {blog_id})")
                    return f"gid://shopify/Blog/{blog_id}"
        
        # Blog doesn't exist, create it
        logger.info(f"Blog '{blog_title}' not found. Creating new blog...")
        
        blog_data = {
            "blog": {
                "title": blog_title
            }
        }
        
        rest_response = self._make_rest_request('POST', 'blogs.json', blog_data)
        
        if 'errors' in rest_response:
            logger.error(f"Error creating blog: {rest_response['errors']}")
            return None
        
        if 'blog' in rest_response:
            blog_id = rest_response['blog']['id']
            logger.info(f"Created new blog: {blog_title} (ID: {blog_id})")
            return f"gid://shopify/Blog/{blog_id}"
        
        logger.error("Failed to create blog - unexpected response format")
        return None
    
    def check_article_exists(self, blog_id: str, handle: str) -> bool:
        """Check if an article with the given handle already exists"""
        blog_numeric_id = blog_id.split('/')[-1] if '/' in blog_id else blog_id
        
        # Get all articles for this blog
        rest_response = self._make_rest_request('GET', f'blogs/{blog_numeric_id}/articles.json')
        
        if 'errors' in rest_response:
            return False
        
        if 'articles' in rest_response:
            for article in rest_response['articles']:
                if article.get('handle') == handle:
                    return True
        
        return False
    
    def parse_html_blog(self, html_file_path: str) -> Tuple[str, str]:
        """Parse HTML file and extract title and content"""
        logger.info(f"Parsing HTML file: {html_file_path}")
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Use BeautifulSoup to parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract title from h1 tag
        h1_tag = soup.find('h1')
        if h1_tag:
            title = h1_tag.get_text(strip=True)
        else:
            # Fallback: use filename
            title = Path(html_file_path).stem.replace('-', ' ').title()
        
        # Extract all content (remove h1, keep everything else)
        if h1_tag:
            h1_tag.decompose()
        
        # Get the body content
        content_html = str(soup)
        
        # Clean up the HTML - remove any remaining body/html tags if present
        content_html = re.sub(r'^<html[^>]*>', '', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'</html>$', '', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'^<body[^>]*>', '', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'</body>$', '', content_html, flags=re.IGNORECASE)
        content_html = content_html.strip()
        
        logger.info(f"Extracted title: {title}")
        logger.info(f"Content length: {len(content_html)} characters")
        
        return title, content_html
    
    def create_blog_article(self, blog_id: str, title: str, content_html: str, author: str = "RezaGemCollection", skip_existing: bool = True) -> Optional[str]:
        """Create a blog article in Shopify. Returns article ID if successful."""
        logger.info(f"Creating blog article: {title}")
        
        # Generate handle from title
        handle = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        handle = handle[:255]  # Shopify handle limit
        
        # Check if article already exists
        if skip_existing and self.check_article_exists(blog_id, handle):
            logger.info(f"Article with handle '{handle}' already exists. Skipping...")
            return "SKIPPED"
        
        # Extract numeric blog ID from GraphQL ID
        blog_numeric_id = blog_id.split('/')[-1] if '/' in blog_id else blog_id
        
        article_data = {
            "article": {
                "title": title,
                "body_html": content_html,
                "author": author
            }
        }
        
        rest_response = self._make_rest_request('POST', f'blogs/{blog_numeric_id}/articles.json', article_data)
        
        if 'errors' in rest_response:
            logger.error(f"REST API errors: {rest_response['errors']}")
            return None
        
        if 'article' in rest_response:
            article_id = rest_response['article']['id']
            logger.info(f"[SUCCESS] Created article: {title} (ID: {article_id})")
            return f"gid://shopify/Article/{article_id}"
        
        logger.error("Failed to create article via REST API")
        return None
    
    def send_all_blogs(self, htmls_dir: str = "htmls", blog_title: str = "Blog", skip_existing: bool = True):
        """Send all HTML blog files to Shopify"""
        logger.info("="*60)
        logger.info("STARTING BATCH BLOG UPLOAD")
        logger.info("="*60)
        
        htmls_path = Path(htmls_dir)
        if not htmls_path.exists():
            logger.error(f"Directory '{htmls_dir}' not found!")
            return
        
        html_files = list(htmls_path.glob("*.html"))
        if not html_files:
            logger.error(f"No HTML files found in '{htmls_dir}' directory!")
            return
        
        logger.info(f"Found {len(html_files)} HTML files to process")
        logger.info("")
        
        # Get or create blog
        blog_id = self.get_or_create_blog(blog_title)
        if not blog_id:
            logger.error("Failed to get or create blog. Aborting.")
            return
        
        logger.info("")
        logger.info("="*60)
        logger.info("PROCESSING BLOG FILES")
        logger.info("="*60)
        logger.info("")
        
        # Process each file
        for idx, html_file in enumerate(html_files, 1):
            logger.info(f"[{idx}/{len(html_files)}] Processing: {html_file.name}")
            logger.info("-" * 60)
            
            try:
                # Parse HTML
                title, content_html = self.parse_html_blog(str(html_file))
                
                # Create article
                article_id = self.create_blog_article(blog_id, title, content_html, skip_existing=skip_existing)
                
                if article_id == "SKIPPED":
                    self.results['skipped'].append({
                        'file': html_file.name,
                        'title': title,
                        'reason': 'Already exists'
                    })
                    logger.info(f"[SKIPPED] {html_file.name}")
                elif article_id:
                    self.results['success'].append({
                        'file': html_file.name,
                        'title': title,
                        'article_id': article_id
                    })
                    logger.info(f"[SUCCESS] {html_file.name}")
                else:
                    self.results['failed'].append({
                        'file': html_file.name,
                        'title': title,
                        'reason': 'Unknown error'
                    })
                    logger.error(f"[FAILED] {html_file.name}")
                
            except Exception as e:
                logger.error(f"Error processing {html_file.name}: {e}", exc_info=True)
                self.results['failed'].append({
                    'file': html_file.name,
                    'title': 'Unknown',
                    'reason': str(e)
                })
            
            # Rate limiting - be nice to Shopify API
            if idx < len(html_files):
                time.sleep(1)  # 1 second delay between requests
            
            logger.info("")
        
        # Print summary
        self.print_summary()
        
        # Save results to JSON
        results_file = f"blog_send_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {results_file}")
    
    def print_summary(self):
        """Print summary of results"""
        logger.info("")
        logger.info("="*60)
        logger.info("SUMMARY")
        logger.info("="*60)
        logger.info(f"Total processed: {len(self.results['success']) + len(self.results['failed']) + len(self.results['skipped'])}")
        logger.info(f"Successful: {len(self.results['success'])}")
        logger.info(f"Failed: {len(self.results['failed'])}")
        logger.info(f"Skipped (already exist): {len(self.results['skipped'])}")
        logger.info("")
        
        if self.results['success']:
            logger.info("Successfully created articles:")
            for item in self.results['success']:
                logger.info(f"  - {item['title']}")
            logger.info("")
        
        if self.results['failed']:
            logger.error("Failed articles:")
            for item in self.results['failed']:
                logger.error(f"  - {item['file']}: {item.get('reason', 'Unknown error')}")
            logger.error("")
        
        if self.results['skipped']:
            logger.info("Skipped articles (already exist):")
            for item in self.results['skipped']:
                logger.info(f"  - {item['title']}")
            logger.info("")


def main():
    """Main function to send all blogs"""
    try:
        sender = ShopifyBlogSender()
        
        # Send all blogs
        sender.send_all_blogs(
            htmls_dir="htmls",
            blog_title="Blog",
            skip_existing=True  # Set to False to create duplicates
        )
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    main()











