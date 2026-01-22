import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
from bs4 import BeautifulSoup
import re
import threading
import json
from typing import List, Tuple, Dict
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LinkForgeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LinkForge - Internal Link Automation")
        self.root.geometry("800x700")
        self.root.configure(bg="#f5f5f5")
        
        # Load Shopify credentials from environment
        self.shopify_store = os.getenv('SHOPIFY_SHOP_NAME', '').strip()
        self.shopify_token = os.getenv('SHOPIFY_API_PASSWORD', '').strip()
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = tk.Frame(self.root, bg="#f5f5f5", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Label(
            main_frame,
            text="🔗 LinkForge",
            font=("Arial", 24, "bold"),
            bg="#f5f5f5",
            fg="#2c3e50"
        )
        header.pack(pady=(0, 20))
        
        # Input fields
        input_frame = tk.LabelFrame(
            main_frame,
            text="Configuration",
            font=("Arial", 10, "bold"),
            bg="#f5f5f5",
            padx=15,
            pady=15
        )
        input_frame.pack(fill=tk.X, pady=10)
        
        # Keywords
        tk.Label(input_frame, text="Keywords (comma-separated):", bg="#f5f5f5").grid(row=0, column=0, sticky="w", pady=5)
        self.words_var = tk.StringVar()
        tk.Entry(input_frame, textvariable=self.words_var, width=50).grid(row=0, column=1, pady=5, padx=10)
        
        # Collection URL with dropdown
        tk.Label(input_frame, text="Collection URL:", bg="#f5f5f5").grid(row=1, column=0, sticky="w", pady=5)
        collection_frame = tk.Frame(input_frame, bg="#f5f5f5")
        collection_frame.grid(row=1, column=1, pady=5, padx=10, sticky="ew")
        
        self.collection_url_var = tk.StringVar()
        self.collection_entry = tk.Entry(collection_frame, textvariable=self.collection_url_var, width=40)
        self.collection_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Load collections button
        load_btn = tk.Button(
            collection_frame,
            text="Load from JSON",
            command=self.load_collections_dropdown,
            bg="#95a5a6",
            fg="white",
            font=("Arial", 9),
            padx=10
        )
        load_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Collection dropdown row (searchable)
        tk.Label(input_frame, text="Select Collection:", bg="#f5f5f5", font=("Arial", 9)).grid(row=2, column=0, sticky="w", pady=5)
        dropdown_frame = tk.Frame(input_frame, bg="#f5f5f5")
        dropdown_frame.grid(row=2, column=1, pady=5, padx=10, sticky="ew")
        dropdown_frame.columnconfigure(0, weight=1)
        
        # Create searchable combobox - fully editable
        self.collection_dropdown = ttk.Combobox(
            dropdown_frame,
            width=47,
            state="normal"  # "normal" allows typing
        )
        self.collection_dropdown.grid(row=0, column=0, sticky="ew", padx=0)
        
        # Set placeholder text
        self.collection_placeholder = "Type to search collections..."
        self.collection_dropdown.insert(0, self.collection_placeholder)
        self.collection_dropdown.config(foreground="gray")
        
        # Bind events for searchable dropdown
        self.collection_dropdown.bind("<FocusIn>", self.on_dropdown_focus_in)
        self.collection_dropdown.bind("<FocusOut>", self.on_dropdown_focus_out)
        self.collection_dropdown.bind("<<ComboboxSelected>>", self.on_collection_selected)
        self.collection_dropdown.bind("<KeyRelease>", self.on_collection_search)
        self.collection_dropdown.bind("<Return>", self.on_collection_enter)
        self.collection_dropdown.bind("<Button-1>", self.on_dropdown_click)
        
        # Store all collections and filtered list
        self.collections_data = []
        self.all_collection_titles = []
        self.placeholder_active = True
        
        # Link URL
        tk.Label(input_frame, text="Link URL:", bg="#f5f5f5").grid(row=3, column=0, sticky="w", pady=5)
        self.link_url_var = tk.StringVar()
        tk.Entry(input_frame, textvariable=self.link_url_var, width=50).grid(row=3, column=1, pady=5, padx=10)
        
        # Shopify status
        status_frame = tk.Frame(main_frame, bg="#f5f5f5")
        status_frame.pack(fill=tk.X, pady=10)
        status_text = "✅ Connected" if self.shopify_token else "⚠️ Not configured (check .env file)"
        status_color = "#2ecc71" if self.shopify_token else "#f39c12"
        tk.Label(status_frame, text=f"Shopify: {status_text}", bg="#f5f5f5", fg=status_color).pack()
        
        # Process button
        self.process_btn = tk.Button(
            main_frame,
            text="Process Collection",
            command=self.start_processing,
            bg="#3498db",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10
        )
        self.process_btn.pack(pady=15)
        
        # Output log
        log_frame = tk.LabelFrame(
            main_frame,
            text="Processing Log",
            font=("Arial", 10, "bold"),
            bg="#f5f5f5",
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.output_text = tk.Text(
            log_frame,
            font=("Consolas", 10),
            bg="white",
            fg="black",
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set
        )
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.output_text.yview)
        
        self.log("LinkForge Ready - Fill in the form and click 'Process Collection'")
        # Try to auto-load collections on startup
        self.load_collections_dropdown()
    
    def log(self, message):
        """Add message to log"""
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def load_collections_dropdown(self):
        """Load collections from JSON file and populate dropdown"""
        try:
            # Path to collections.json in Collection Manager folder
            json_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'Collection Manager',
                'collections.json'
            )
            json_path = os.path.normpath(json_path)
            
            if not os.path.exists(json_path):
                self.log("⚠️ Collections JSON not found. Fetch collections first using Collection Manager app.")
                self.collection_dropdown['values'] = []
                self.all_collection_titles = []
                return
            
            with open(json_path, 'r', encoding='utf-8') as f:
                self.collections_data = json.load(f)
            
            if not self.collections_data:
                self.log("⚠️ Collections JSON is empty. Fetch collections first.")
                self.collection_dropdown['values'] = []
                self.all_collection_titles = []
                return
            
            # Populate combobox with collection titles (searchable format)
            self.all_collection_titles = [
                f"{col.get('title', 'Unknown')} ({col.get('handle', '')})" 
                for col in self.collections_data
            ]
            self.collection_dropdown['values'] = self.all_collection_titles
            
            self.log(f"✅ Loaded {len(self.collections_data)} collections from JSON")
            self.log("💡 Tip: Type in the dropdown to search collections by title or handle")
            
        except Exception as e:
            self.log(f"⚠️ Error loading collections: {e}")
            self.collection_dropdown['values'] = []
            self.all_collection_titles = []
    
    def on_dropdown_click(self, event=None):
        """Handle click on dropdown"""
        if self.placeholder_active:
            self.collection_dropdown.delete(0, tk.END)
            self.collection_dropdown.config(foreground="black")
            self.placeholder_active = False
    
    def on_dropdown_focus_in(self, event=None):
        """Clear placeholder when user focuses"""
        if self.placeholder_active:
            self.collection_dropdown.delete(0, tk.END)
            self.collection_dropdown.config(foreground="black")
            self.placeholder_active = False
    
    def on_dropdown_focus_out(self, event=None):
        """Restore placeholder if empty"""
        current_text = self.collection_dropdown.get().strip()
        if not current_text:
            self.collection_dropdown.insert(0, self.collection_placeholder)
            self.collection_dropdown.config(foreground="gray")
            self.placeholder_active = True
    
    def on_collection_search(self, event=None):
        """Filter collections as user types"""
        try:
            # Don't filter on arrow keys or special keys
            if event and event.keysym in ['Up', 'Down', 'Return', 'Tab', 'Escape', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R']:
                return
            
            # Get current text
            search_text = self.collection_dropdown.get()
            
            # Remove placeholder if active
            if self.placeholder_active or search_text == self.collection_placeholder:
                search_text = ""
                self.collection_dropdown.delete(0, tk.END)
                self.collection_dropdown.config(foreground="black")
                self.placeholder_active = False
            
            search_text = search_text.lower().strip()
            
            if not search_text:
                # Show all if search is empty
                self.collection_dropdown['values'] = self.all_collection_titles
                return
            
            # Filter collections by title or handle
            filtered = []
            for i, title in enumerate(self.all_collection_titles):
                collection = self.collections_data[i]
                title_lower = title.lower()
                handle_lower = collection.get('handle', '').lower()
                
                # Search in title or handle
                if search_text in title_lower or search_text in handle_lower:
                    filtered.append(title)
            
            # Update dropdown values with filtered results
            self.collection_dropdown['values'] = filtered
            
            # Ensure combobox stays editable and focused
            self.collection_dropdown.config(state="normal")
            
        except Exception as e:
            pass
    
    def on_collection_enter(self, event=None):
        """Handle Enter key - select first match if typing"""
        try:
            search_text = self.collection_dropdown.get()
            if not search_text:
                return
            
            # Find exact or first partial match
            for i, title in enumerate(self.all_collection_titles):
                if search_text.lower() in title.lower():
                    # Select this collection
                    self.collection_dropdown.current(i)
                    self.on_collection_selected()
                    break
        except:
            pass
    
    def on_collection_selected(self, event=None):
        """Handle collection selection from dropdown"""
        try:
            selected_text = self.collection_dropdown.get()
            if not selected_text or selected_text == self.collection_placeholder:
                return
            
            # Find the collection by matching the selected text
            for i, title in enumerate(self.all_collection_titles):
                if title == selected_text or selected_text in title:
                    if i < len(self.collections_data):
                        collection = self.collections_data[i]
                        handle = collection.get('handle', '')
                        if handle:
                            url = f"https://rezagemcollection.ca/collections/{handle}"
                            self.collection_url_var.set(url)
                            # Auto-fill Link URL with the same URL (but it's still editable)
                            self.link_url_var.set(url)
                            self.log(f"✅ Selected: {collection.get('title', 'Unknown')}")
                            self.log(f"   Collection URL and Link URL set to: {url}")
                            # Keep field editable - ensure state is normal
                            self.collection_dropdown.config(state="normal")
                            self.placeholder_active = False
                            # Allow user to continue typing or delete
                            return
            
            # If no exact match, try to find by handle in the typed text
            search_text = selected_text.lower()
            for collection in self.collections_data:
                handle = collection.get('handle', '').lower()
                title = collection.get('title', '').lower()
                if search_text in handle or search_text in title:
                    url = f"https://rezagemcollection.ca/collections/{collection.get('handle', '')}"
                    self.collection_url_var.set(url)
                    self.link_url_var.set(url)
                    self.log(f"✅ Found: {collection.get('title', 'Unknown')}")
                    self.log(f"   Collection URL and Link URL set to: {url}")
                    # Keep field editable
                    self.collection_dropdown.config(state="normal")
                    self.placeholder_active = False
                    return
                    
        except Exception as e:
            self.log(f"⚠️ Error selecting collection: {e}")
            # Ensure it stays editable even on error
            self.collection_dropdown.config(state="normal")
    
    def get_collection_products(self, collection_url: str) -> List[str]:
        """Get all product URLs from a collection"""
        try:
            handle = collection_url.split('/collections/')[-1].split('?')[0].split('#')[0]
            json_url = f"https://rezagemcollection.ca/collections/{handle}.json"
            
            response = requests.get(json_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                products = data.get('collection', {}).get('products', [])
                if products:
                    return [f"https://rezagemcollection.ca/products/{p.get('handle', '')}" for p in products]
            
            # Fallback: HTML scraping
            response = requests.get(collection_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            product_links = soup.find_all('a', href=re.compile(r'/products/'))
            
            seen = set()
            products = []
            for link in product_links:
                href = link.get('href', '')
                if '/products/' in href:
                    handle = href.split('/products/')[-1].split('?')[0].split('#')[0].strip()
                    if handle and handle not in seen:
                        seen.add(handle)
                        products.append(f"https://rezagemcollection.ca/products/{handle}")
            
            return products
        except Exception as e:
            self.log(f"Error fetching products: {e}")
            return []
    
    def get_product_description(self, product_url: str) -> Tuple[str, str]:
        """Get product description HTML and product ID"""
        try:
            handle = product_url.split('/products/')[-1].split('?')[0]
            json_url = f"https://rezagemcollection.ca/products/{handle}.json"
            
            response = requests.get(json_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                product = data.get('product', {})
                description = product.get('body_html', '')
                product_id = product.get('id', '')
                product_gid = f"gid://shopify/Product/{product_id}" if product_id else ""
                return description, product_gid
            return "", ""
        except Exception as e:
            self.log(f"  Error: {e}")
            return "", ""
    
    def add_link_to_word(self, html: str, word: str, link_url: str) -> str:
        """Add link to word in paragraphs under Product Description h2"""
        if not html:
            return html
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the Product Description h2
        h2 = None
        for tag in soup.find_all('h2'):
            if 'Product Description' in tag.get_text():
                h2 = tag
                break
        
        if not h2:
            return html
        
        # Find all paragraphs after this h2
        paragraphs = []
        found_h2 = False
        for tag in soup.find_all(['h2', 'p']):
            if tag == h2:
                found_h2 = True
                continue
            if found_h2:
                if tag.name == 'p':
                    paragraphs.append(tag)
                elif tag.name == 'h2':
                    break
        
        # Find and link the word in paragraphs - work with HTML string directly
        for p in paragraphs:
            text = p.get_text()
            if word.lower() not in text.lower():
                continue
            
            # Check if already linked
            links = p.find_all('a', href=True)
            for link in links:
                if link_url in link.get('href', '') and word.lower() in link.get_text().lower():
                    return html  # Already linked
            
            # Get the exact paragraph HTML from original HTML
            p_html = str(p)
            
            # Add link using regex
            pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
            
            def replace(match):
                before = p_html[:match.start()]
                open_a = before.count('<a ') - before.count('</a>')
                if open_a > 0:
                    return match.group(0)
                return f'<a href="{link_url}">{match.group(1)}</a>'
            
            new_p_html = pattern.sub(replace, p_html, count=1)
            
            # Only replace if link was actually added
            if new_p_html != p_html and link_url in new_p_html:
                # Replace the paragraph in the full HTML string
                html = html.replace(p_html, new_p_html, 1)
                return html  # Return immediately after first successful link
        
        return html
    
    def update_product(self, product_gid: str, html: str) -> bool:
        """Update product on Shopify"""
        if not self.shopify_token or not self.shopify_store:
            return False
        
        shop = self.shopify_store
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        
        try:
            url = f"https://{shop}/admin/api/2024-01/graphql.json"
            headers = {
                'X-Shopify-Access-Token': self.shopify_token,
                'Content-Type': 'application/json'
            }
            
            mutation = """
            mutation productUpdate($input: ProductInput!) {
              productUpdate(input: $input) {
                product { id title }
                userErrors { field message }
              }
            }
            """
            
            response = requests.post(
                url,
                json={'query': mutation, 'variables': {'input': {'id': product_gid, 'descriptionHtml': html}}},
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'errors' in result:
                    return False
                errors = result.get('data', {}).get('productUpdate', {}).get('userErrors', [])
                return len(errors) == 0
            return False
        except:
            return False
    
    def process_product(self, product_url: str, words: List[str], link_url: str):
        """Process a single product"""
        description, product_gid = self.get_product_description(product_url)
        
        if not description:
            return {'status': 'error', 'message': 'No description'}
        
        # Check if already linked
        for word in words:
            soup = BeautifulSoup(description, 'html.parser')
            h2 = None
            for tag in soup.find_all('h2'):
                if 'Product Description' in tag.get_text():
                    h2 = tag
                    break
            if h2:
                found_h2 = False
                for tag in soup.find_all(['h2', 'p']):
                    if tag == h2:
                        found_h2 = True
                        continue
                    if found_h2 and tag.name == 'p':
                        links = tag.find_all('a', href=True)
                        for link in links:
                            if link_url in link.get('href', '') and word.lower() in link.get_text().lower():
                                return {'status': 'already_linked', 'word': word}
        
        # Add links
        updated_html = description
        linked_count = 0
        for word in words:
            new_html = self.add_link_to_word(updated_html, word, link_url)
            if new_html != updated_html:
                updated_html = new_html
                linked_count += 1
        
        if linked_count == 0:
            return {'status': 'no_match'}
        
        # Update Shopify
        updated = False
        if product_gid and self.shopify_token:
            updated = self.update_product(product_gid, updated_html)
        
        return {'status': 'success', 'linked': linked_count, 'updated': updated}
    
    def start_processing(self):
        """Start processing"""
        words_str = self.words_var.get().strip()
        collection_url = self.collection_url_var.get().strip()
        link_url = self.link_url_var.get().strip()
        
        if not all([words_str, collection_url, link_url]):
            messagebox.showwarning("Missing Information", "Please fill in all fields!")
            return
        
        words = [w.strip() for w in words_str.split(',')]
        self.output_text.delete(1.0, tk.END)
        self.process_btn.config(state=tk.DISABLED)
        
        def process():
            try:
                self.log(f"Fetching products from collection...")
                products = self.get_collection_products(collection_url)
                self.log(f"Found {len(products)} products\n")
                
                if not products:
                    self.log("No products found!")
                    self.process_btn.config(state=tk.NORMAL)
                    return
                
                results = {'success': 0, 'already_linked': 0, 'no_match': 0, 'error': 0}
                
                for i, product_url in enumerate(products, 1):
                    self.log(f"[{i}/{len(products)}] {product_url.split('/products/')[-1]}")
                    
                    result = self.process_product(product_url, words, link_url)
                    
                    if result['status'] == 'success':
                        self.log(f"  ✅ Linked {result.get('linked', 0)} word(s)")
                        if result.get('updated'):
                            self.log(f"  ✅ Updated on Shopify")
                        results['success'] += 1
                    elif result['status'] == 'already_linked':
                        self.log(f"  ⚠️  '{result.get('word')}' already linked")
                        results['already_linked'] += 1
                    elif result['status'] == 'no_match':
                        self.log(f"  ⚠️  Keywords not found")
                        results['no_match'] += 1
                    else:
                        self.log(f"  ❌ Error: {result.get('message')}")
                        results['error'] += 1
                
                self.log(f"\n✅ Success: {results['success']}")
                self.log(f"⚠️  Already linked: {results['already_linked']}")
                self.log(f"⚠️  No match: {results['no_match']}")
                self.log(f"❌ Errors: {results['error']}")
                
                messagebox.showinfo("Complete", f"Processed {len(products)} products!")
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.process_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=process, daemon=True).start()

def main():
    root = tk.Tk()
    app = LinkForgeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
