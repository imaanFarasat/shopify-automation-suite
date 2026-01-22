import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import json
import os
import re
import threading
from dotenv import load_dotenv
from typing import List, Dict
from pathlib import Path

# Load environment variables
load_dotenv()

class CollectionDescriptionFetcher:
    def __init__(self, root):
        self.root = root
        self.root.title("Collection Description Manager")
        self.root.geometry("800x700")
        self.root.configure(bg="#f5f5f5")
        
        # Load Shopify credentials
        self.shopify_store = os.getenv('SHOPIFY_SHOP_NAME', '').strip()
        self.shopify_token = os.getenv('SHOPIFY_API_PASSWORD', '').strip()
        
        # Base folder for descriptions
        self.base_folder = os.path.join(os.path.dirname(__file__), 'descriptions')
        os.makedirs(self.base_folder, exist_ok=True)
        
        # Load collections from JSON
        self.collections_json_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'Collection Manager',
            'collections.json'
        )
        
        self.setup_ui()
        self.load_stats()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_frame = tk.Frame(self.root, bg="#f5f5f5", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Label(
            main_frame,
            text="📝 Collection Description Manager",
            font=("Arial", 24, "bold"),
            bg="#f5f5f5",
            fg="#2c3e50"
        )
        header.pack(pady=(0, 20))
        
        # Status
        status_frame = tk.Frame(main_frame, bg="#f5f5f5")
        status_frame.pack(fill=tk.X, pady=10)
        status_text = "✅ Connected" if self.shopify_token else "⚠️ Not configured (check .env file)"
        status_color = "#2ecc71" if self.shopify_token else "#f39c12"
        tk.Label(status_frame, text=f"Shopify: {status_text}", bg="#f5f5f5", fg=status_color).pack()
        
        # Stats
        self.stats_label = tk.Label(
            main_frame,
            text="Collections: 0 | Fetched: 0",
            font=("Arial", 11),
            bg="#f5f5f5",
            fg="#7f8c8d"
        )
        self.stats_label.pack(pady=10)
        
        # Collection selector for fetching products
        products_frame = tk.LabelFrame(
            main_frame,
            text="Fetch Collection Products",
            font=("Arial", 10, "bold"),
            bg="#f5f5f5",
            padx=15,
            pady=15
        )
        products_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(products_frame, text="Select Collection:", bg="#f5f5f5").pack(side=tk.LEFT, padx=5)
        
        self.collection_var = tk.StringVar()
        self.collection_dropdown = ttk.Combobox(
            products_frame,
            textvariable=self.collection_var,
            width=40,
            state="normal"  # "normal" allows typing/searching
        )
        self.collection_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Set placeholder text
        self.collection_placeholder = "Type to search collections..."
        self.collection_dropdown.insert(0, self.collection_placeholder)
        self.collection_dropdown.config(foreground="gray")
        self.placeholder_active = True
        
        # Bind events for searchable dropdown
        self.collection_dropdown.bind("<FocusIn>", self.on_dropdown_focus_in)
        self.collection_dropdown.bind("<FocusOut>", self.on_dropdown_focus_out)
        self.collection_dropdown.bind("<KeyRelease>", self.on_collection_search)
        self.collection_dropdown.bind("<<ComboboxSelected>>", self.on_collection_selected)
        self.collection_dropdown.bind("<Return>", self.on_collection_enter)
        self.collection_dropdown.bind("<Button-1>", self.on_dropdown_click)
        
        # Store all collections and filtered list
        self.collections_data = []
        self.all_collection_titles = []
        
        self.fetch_products_btn = tk.Button(
            products_frame,
            text="Fetch Products",
            command=self.fetch_collection_products,
            bg="#9b59b6",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=15,
            pady=5
        )
        self.fetch_products_btn.pack(side=tk.LEFT, padx=5)
        
        # Upload Collection Description section
        upload_frame = tk.LabelFrame(
            main_frame,
            text="Upload Collection Description",
            font=("Arial", 10, "bold"),
            bg="#f5f5f5",
            padx=15,
            pady=15
        )
        upload_frame.pack(fill=tk.X, pady=10)
        
        # Collection selector for upload
        tk.Label(upload_frame, text="Select Collection:", bg="#f5f5f5").pack(side=tk.LEFT, padx=5)
        
        self.upload_collection_var = tk.StringVar()
        self.upload_collection_dropdown = ttk.Combobox(
            upload_frame,
            textvariable=self.upload_collection_var,
            width=35,
            state="normal"
        )
        self.upload_collection_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Set placeholder for upload dropdown
        self.upload_collection_dropdown.insert(0, self.collection_placeholder)
        self.upload_collection_dropdown.config(foreground="gray")
        self.upload_placeholder_active = True
        
        # Bind events for upload dropdown
        self.upload_collection_dropdown.bind("<FocusIn>", self.on_upload_dropdown_focus_in)
        self.upload_collection_dropdown.bind("<FocusOut>", self.on_upload_dropdown_focus_out)
        self.upload_collection_dropdown.bind("<KeyRelease>", self.on_upload_collection_search)
        self.upload_collection_dropdown.bind("<<ComboboxSelected>>", self.on_upload_collection_selected)
        self.upload_collection_dropdown.bind("<Return>", self.on_upload_collection_enter)
        self.upload_collection_dropdown.bind("<Button-1>", self.on_upload_dropdown_click)
        
        # File selection
        file_frame = tk.Frame(upload_frame, bg="#f5f5f5")
        file_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(file_frame, text="HTML File:", bg="#f5f5f5").pack(side=tk.LEFT, padx=5)
        
        self.file_path_var = tk.StringVar()
        self.file_path_entry = tk.Entry(file_frame, textvariable=self.file_path_var, width=50, state="readonly")
        self.file_path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.browse_btn = tk.Button(
            file_frame,
            text="Browse",
            command=self.browse_html_file,
            bg="#95a5a6",
            fg="white",
            font=("Arial", 10),
            padx=10,
            pady=5
        )
        self.browse_btn.pack(side=tk.LEFT, padx=5)
        
        self.upload_btn = tk.Button(
            upload_frame,
            text="Upload Description",
            command=self.upload_collection_description,
            bg="#e67e22",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=15,
            pady=5
        )
        self.upload_btn.pack(pady=5)
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg="#f5f5f5")
        button_frame.pack(pady=20)
        
        self.fetch_btn = tk.Button(
            button_frame,
            text="Fetch All Descriptions",
            command=self.fetch_all_descriptions,
            bg="#3498db",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            width=20
        )
        self.fetch_btn.pack(side=tk.LEFT, padx=10)
        
        self.update_btn = tk.Button(
            button_frame,
            text="Update (New/Changed)",
            command=self.update_descriptions,
            bg="#2ecc71",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            width=20
        )
        self.update_btn.pack(side=tk.LEFT, padx=10)
        
        # Log area
        log_frame = tk.LabelFrame(
            main_frame,
            text="Activity Log",
            font=("Arial", 10, "bold"),
            bg="#f5f5f5",
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(
            log_frame,
            font=("Consolas", 10),
            bg="white",
            fg="black",
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        self.log("Collection Description Manager Ready")
        
        # Load collections into dropdown after UI is ready
        self.load_collections_dropdown()
    
    def load_collections_dropdown(self):
        """Load collections into the dropdown"""
        try:
            collections = self.load_collections()
            if collections:
                self.collections_data = collections
                # Populate combobox with collection titles (searchable format)
                self.all_collection_titles = [
                    f"{col.get('title', 'Unknown')} ({col.get('handle', '')})" 
                    for col in self.collections_data
                ]
                self.collection_dropdown['values'] = self.all_collection_titles
                if hasattr(self, 'log_text'):
                    self.log(f"✅ Loaded {len(self.collections_data)} collections from JSON")
                    self.log("💡 Tip: Type in the dropdown to search collections by title or handle")
        except Exception as e:
            if hasattr(self, 'log_text'):
                self.log(f"⚠️ Error loading collections: {e}")
            else:
                print(f"Error loading collections: {e}")
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
            
            # Keep field editable
            self.collection_dropdown.config(state="normal")
            self.placeholder_active = False
            
        except Exception as e:
            # Ensure it stays editable even on error
            self.collection_dropdown.config(state="normal")
    
    def log(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def load_stats(self):
        """Load and display statistics"""
        try:
            # Count collections in JSON
            if os.path.exists(self.collections_json_path):
                with open(self.collections_json_path, 'r', encoding='utf-8') as f:
                    collections = json.load(f)
                total_collections = len(collections)
            else:
                total_collections = 0
            
            # Count fetched descriptions
            fetched_count = 0
            if os.path.exists(self.base_folder):
                for item in os.listdir(self.base_folder):
                    item_path = os.path.join(self.base_folder, item)
                    if os.path.isdir(item_path):
                        # Check if it has description.html
                        desc_file = os.path.join(item_path, 'description.html')
                        if os.path.exists(desc_file):
                            fetched_count += 1
            
            self.stats_label.config(text=f"Collections: {total_collections} | Fetched: {fetched_count}")
        except:
            pass
    
    def load_collections(self) -> List[Dict]:
        """Load collections from JSON file"""
        try:
            if not os.path.exists(self.collections_json_path):
                self.log("⚠️ Collections JSON not found. Use Collection Manager to fetch collections first.")
                return []
            
            with open(self.collections_json_path, 'r', encoding='utf-8') as f:
                collections = json.load(f)
            
            return collections
        except Exception as e:
            self.log(f"⚠️ Error loading collections: {e}")
            return []
    
    def fetch_collection_description(self, collection_id: str, handle: str) -> tuple:
        """Fetch collection description HTML from Shopify
        Returns: (description_html, error_message)
        """
        if not self.shopify_token or not self.shopify_store:
            return ("", "Shopify credentials not configured")
        
        shop = self.shopify_store
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        
        try:
            url = f"https://{shop}/admin/api/2024-01/graphql.json"
            headers = {
                'X-Shopify-Access-Token': self.shopify_token,
                'Content-Type': 'application/json'
            }
            
            query = """
            query getCollection($id: ID!) {
              collection(id: $id) {
                id
                title
                handle
                description
                descriptionHtml
              }
            }
            """
            
            response = requests.post(
                url,
                json={'query': query, 'variables': {'id': collection_id}},
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'errors' in result:
                    error_msg = '; '.join([e.get('message', str(e)) for e in result['errors']])
                    return ("", f"GraphQL error: {error_msg}")
                
                data = result.get('data', {}).get('collection', {})
                if not data:
                    return ("", "Collection not found")
                
                description_html = data.get('descriptionHtml', '')
                if not description_html or description_html.strip() == '':
                    return ("", "No description (empty)")
                
                return (description_html, None)
            
            return ("", f"HTTP {response.status_code}: {response.text[:100]}")
        except Exception as e:
            return ("", f"Exception: {str(e)}")
    
    def save_description(self, handle: str, description_html: str):
        """Save description HTML to folder named by handle"""
        try:
            # Create folder for this collection
            collection_folder = os.path.join(self.base_folder, handle)
            os.makedirs(collection_folder, exist_ok=True)
            
            # Save description.html
            desc_file = os.path.join(collection_folder, 'description.html')
            with open(desc_file, 'w', encoding='utf-8') as f:
                f.write(description_html)
            
            return True
        except Exception as e:
            self.log(f"  Error saving {handle}: {e}")
            return False
    
    def fetch_all_descriptions(self):
        """Fetch all collection descriptions"""
        self.fetch_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log("Fetching all collection descriptions...")
        
        def fetch():
            try:
                collections = self.load_collections()
                
                if not collections:
                    self.log("No collections found!")
                    messagebox.showwarning("Warning", "No collections found. Fetch collections first.")
                    self.fetch_btn.config(state=tk.NORMAL)
                    return
                
                self.log(f"Found {len(collections)} collections\n")
                
                fetched = 0
                errors = 0
                
                for i, collection in enumerate(collections, 1):
                    handle = collection.get('handle', '')
                    title = collection.get('title', 'Unknown')
                    collection_id = collection.get('id', '')
                    
                    if not handle or not collection_id:
                        continue
                    
                    self.log(f"[{i}/{len(collections)}] {title} ({handle})")
                    
                    description_html, error_msg = self.fetch_collection_description(collection_id, handle)
                    
                    if description_html:
                        if self.save_description(handle, description_html):
                            self.log(f"  ✅ Saved")
                            fetched += 1
                        else:
                            self.log(f"  ❌ Save failed")
                            errors += 1
                    else:
                        if error_msg:
                            self.log(f"  ⚠️  {error_msg}")
                        else:
                            self.log(f"  ⚠️  No description or error")
                        errors += 1
                
                self.log(f"\n✅ Fetched: {fetched}")
                self.log(f"❌ Errors: {errors}")
                
                self.load_stats()
                messagebox.showinfo("Complete", f"Fetched {fetched} collection descriptions!")
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=fetch, daemon=True).start()
    
    def update_descriptions(self):
        """Update descriptions - fetch new ones and update existing"""
        self.update_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log("Updating collection descriptions...")
        
        def update():
            try:
                collections = self.load_collections()
                
                if not collections:
                    self.log("No collections found!")
                    messagebox.showwarning("Warning", "No collections found.")
                    self.update_btn.config(state=tk.NORMAL)
                    return
                
                self.log(f"Found {len(collections)} collections\n")
                
                new_count = 0
                updated_count = 0
                unchanged_count = 0
                errors = 0
                
                for i, collection in enumerate(collections, 1):
                    handle = collection.get('handle', '')
                    title = collection.get('title', 'Unknown')
                    collection_id = collection.get('id', '')
                    
                    if not handle or not collection_id:
                        continue
                    
                    # Check if already exists
                    collection_folder = os.path.join(self.base_folder, handle)
                    desc_file = os.path.join(collection_folder, 'description.html')
                    exists = os.path.exists(desc_file)
                    
                    self.log(f"[{i}/{len(collections)}] {title} ({handle})")
                    
                    # Fetch current description
                    description_html, error_msg = self.fetch_collection_description(collection_id, handle)
                    
                    if not description_html:
                        if error_msg:
                            self.log(f"  ⚠️  {error_msg}")
                        else:
                            self.log(f"  ⚠️  No description or error")
                        errors += 1
                        continue
                    
                    # Check if content changed
                    if exists:
                        try:
                            with open(desc_file, 'r', encoding='utf-8') as f:
                                old_content = f.read()
                            
                            if old_content == description_html:
                                self.log(f"  ℹ️  Unchanged")
                                unchanged_count += 1
                                continue
                            else:
                                self.log(f"  🔄 Updating (content changed)")
                        except:
                            self.log(f"  ➕ New (couldn't read old)")
                    
                    # Save description
                    if self.save_description(handle, description_html):
                        if exists:
                            self.log(f"  ✅ Updated")
                            updated_count += 1
                        else:
                            self.log(f"  ✅ New")
                            new_count += 1
                    else:
                        self.log(f"  ❌ Save failed")
                        errors += 1
                
                self.log(f"\n✅ New: {new_count}")
                self.log(f"🔄 Updated: {updated_count}")
                self.log(f"ℹ️  Unchanged: {unchanged_count}")
                self.log(f"❌ Errors: {errors}")
                
                self.load_stats()
                messagebox.showinfo("Update Complete", f"New: {new_count}\nUpdated: {updated_count}\nUnchanged: {unchanged_count}")
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.update_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=update, daemon=True).start()
    
    def fetch_collection_products(self):
        """Fetch all products from selected collection and save to JSON"""
        selected = self.collection_dropdown.get()
        if not selected or selected == self.collection_placeholder:
            messagebox.showwarning("Warning", "Please select a collection first!")
            return
        
        # Extract handle from selection (format: "Title (handle)")
        handle = None
        try:
            # Try to extract from format "Title (handle)"
            if '(' in selected and ')' in selected:
                handle = selected.split('(')[1].split(')')[0].strip()
            else:
                # Try to find by matching title or handle
                search_text = selected.lower()
                for collection in self.collections_data:
                    title = collection.get('title', '').lower()
                    coll_handle = collection.get('handle', '').lower()
                    if search_text in title or search_text in coll_handle:
                        handle = collection.get('handle', '')
                        break
        except:
            pass
        
        if not handle:
            messagebox.showerror("Error", "Could not find collection handle. Please select from the dropdown.")
            return
        
        self.fetch_products_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log(f"Fetching products from collection: {handle}")
        
        def fetch():
            try:
                products = self.fetch_products_from_collection(handle)
                
                if not products:
                    self.log("No products found!")
                    messagebox.showwarning("Warning", "No products found in this collection!")
                    self.fetch_products_btn.config(state=tk.NORMAL)
                    return
                
                # Save to JSON file in collection folder
                collection_folder = os.path.join(self.base_folder, handle)
                os.makedirs(collection_folder, exist_ok=True)
                
                json_file = os.path.join(collection_folder, 'products.json')
                
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(products, f, indent=2, ensure_ascii=False)
                
                self.log(f"\n✅ Saved {len(products)} products to:")
                self.log(f"   {json_file}")
                
                messagebox.showinfo("Complete", f"Fetched {len(products)} products!\n\nSaved to:\n{json_file}")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_products_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=fetch, daemon=True).start()
    
    def fetch_products_from_collection(self, handle: str) -> List[Dict]:
        """Fetch all products from a collection with full details"""
        if not self.shopify_token or not self.shopify_store:
            self.log("⚠️ Shopify credentials not configured")
            return []
        
        shop = self.shopify_store
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        
        products = []
        cursor = None
        has_next = True
        
        try:
            url = f"https://{shop}/admin/api/2024-01/graphql.json"
            headers = {
                'X-Shopify-Access-Token': self.shopify_token,
                'Content-Type': 'application/json'
            }
            
            self.log(f"📦 Fetching products from collection: {handle}")
            
            while has_next:
                query = """
                query getCollectionProducts($handle: String!, $first: Int!, $after: String) {
                  collectionByHandle(handle: $handle) {
                    id
                    products(first: $first, after: $after) {
                      pageInfo {
                        hasNextPage
                        endCursor
                      }
                      edges {
                        node {
                          id
                          title
                          handle
                          description
                          descriptionHtml
                          priceRangeV2 {
                            minVariantPrice {
                              amount
                              currencyCode
                            }
                            maxVariantPrice {
                              amount
                              currencyCode
                            }
                          }
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
                          variants(first: 250) {
                            edges {
                              node {
                                id
                                title
                                price
                                sku
                                barcode
                                inventoryQuantity
                                selectedOptions {
                                  name
                                  value
                                }
                                image {
                                  id
                                  url
                                  altText
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
                
                response = requests.post(
                    url,
                    json={'query': query, 'variables': {
                        'handle': handle,
                        'first': 50,
                        'after': cursor
                    }},
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'errors' in result:
                        self.log(f"❌ GraphQL Error: {result['errors']}")
                        break
                    
                    collection = result.get('data', {}).get('collectionByHandle')
                    if not collection:
                        self.log("❌ Collection not found")
                        break
                    
                    products_data = collection.get('products', {})
                    edges = products_data.get('edges', [])
                    
                    for edge in edges:
                        product = edge.get('node', {})
                        
                        # Format product data
                        product_data = {
                            'id': product.get('id', ''),
                            'title': product.get('title', ''),
                            'handle': product.get('handle', ''),
                            'description': product.get('description', ''),
                            'descriptionHtml': product.get('descriptionHtml', ''),
                            'priceRange': {
                                'min': product.get('priceRangeV2', {}).get('minVariantPrice', {}).get('amount', '0'),
                                'max': product.get('priceRangeV2', {}).get('maxVariantPrice', {}).get('amount', '0'),
                                'currency': product.get('priceRangeV2', {}).get('minVariantPrice', {}).get('currencyCode', 'CAD')
                            },
                            'images': [],
                            'variants': []
                        }
                        
                        # Extract images
                        images = product.get('images', {}).get('edges', [])
                        for img_edge in images:
                            img = img_edge.get('node', {})
                            product_data['images'].append({
                                'id': img.get('id', ''),
                                'url': img.get('url', ''),
                                'altText': img.get('altText', ''),
                                'width': img.get('width', 0),
                                'height': img.get('height', 0)
                            })
                        
                        # Extract variants
                        variants = product.get('variants', {}).get('edges', [])
                        for var_edge in variants:
                            variant = var_edge.get('node', {})
                            variant_img = variant.get('image', {})
                            
                            product_data['variants'].append({
                                'id': variant.get('id', ''),
                                'title': variant.get('title', ''),
                                'price': variant.get('price', '0'),
                                'sku': variant.get('sku', ''),
                                'barcode': variant.get('barcode', ''),
                                'inventoryQuantity': variant.get('inventoryQuantity', 0),
                                'selectedOptions': variant.get('selectedOptions', []),
                                'image': {
                                    'id': variant_img.get('id', ''),
                                    'url': variant_img.get('url', ''),
                                    'altText': variant_img.get('altText', '')
                                } if variant_img else None
                            })
                        
                        products.append(product_data)
                        self.log(f"  ✓ {product_data['title']} ({len(product_data['variants'])} variants, {len(product_data['images'])} images)")
                    
                    page_info = products_data.get('pageInfo', {})
                    has_next = page_info.get('hasNextPage', False)
                    cursor = page_info.get('endCursor')
                else:
                    self.log(f"❌ HTTP Error: {response.status_code}")
                    break
            
            self.log(f"\n✅ Found {len(products)} products")
            return products
        except Exception as e:
            self.log(f"❌ Error fetching products: {e}")
            return []
    
    def on_upload_dropdown_click(self, event=None):
        """Handle click on upload dropdown"""
        if self.upload_placeholder_active:
            self.upload_collection_dropdown.delete(0, tk.END)
            self.upload_collection_dropdown.config(foreground="black")
            self.upload_placeholder_active = False
    
    def on_upload_dropdown_focus_in(self, event=None):
        """Clear placeholder when user focuses"""
        if self.upload_placeholder_active:
            self.upload_collection_dropdown.delete(0, tk.END)
            self.upload_collection_dropdown.config(foreground="black")
            self.upload_placeholder_active = False
    
    def on_upload_dropdown_focus_out(self, event=None):
        """Restore placeholder if empty"""
        current_text = self.upload_collection_dropdown.get().strip()
        if not current_text:
            self.upload_collection_dropdown.insert(0, self.collection_placeholder)
            self.upload_collection_dropdown.config(foreground="gray")
            self.upload_placeholder_active = True
    
    def on_upload_collection_search(self, event=None):
        """Filter collections as user types in upload dropdown"""
        try:
            if event and event.keysym in ['Up', 'Down', 'Return', 'Tab', 'Escape', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R']:
                return
            
            search_text = self.upload_collection_dropdown.get()
            
            if self.upload_placeholder_active or search_text == self.collection_placeholder:
                search_text = ""
                self.upload_collection_dropdown.delete(0, tk.END)
                self.upload_collection_dropdown.config(foreground="black")
                self.upload_placeholder_active = False
            
            search_text = search_text.lower().strip()
            
            if not search_text:
                self.upload_collection_dropdown['values'] = self.all_collection_titles
                return
            
            filtered = []
            for i, title in enumerate(self.all_collection_titles):
                collection = self.collections_data[i]
                title_lower = title.lower()
                handle_lower = collection.get('handle', '').lower()
                
                if search_text in title_lower or search_text in handle_lower:
                    filtered.append(title)
            
            self.upload_collection_dropdown['values'] = filtered
            self.upload_collection_dropdown.config(state="normal")
        except Exception as e:
            pass
    
    def on_upload_collection_enter(self, event=None):
        """Handle Enter key in upload dropdown"""
        try:
            search_text = self.upload_collection_dropdown.get()
            if not search_text:
                return
            
            for i, title in enumerate(self.all_collection_titles):
                if search_text.lower() in title.lower():
                    self.upload_collection_dropdown.current(i)
                    self.on_upload_collection_selected()
                    break
        except:
            pass
    
    def on_upload_collection_selected(self, event=None):
        """Handle collection selection from upload dropdown"""
        try:
            selected_text = self.upload_collection_dropdown.get()
            if not selected_text or selected_text == self.collection_placeholder:
                return
            
            self.upload_collection_dropdown.config(state="normal")
            self.upload_placeholder_active = False
        except Exception as e:
            self.upload_collection_dropdown.config(state="normal")
    
    def browse_html_file(self):
        """Browse for HTML file to upload"""
        file_path = filedialog.askopenfilename(
            title="Select HTML File",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        
        if file_path:
            self.file_path_var.set(file_path)
            self.log(f"Selected file: {file_path}")
    
    def upload_collection_description(self):
        """Upload collection description to Shopify"""
        selected = self.upload_collection_dropdown.get()
        if not selected or selected == self.collection_placeholder:
            messagebox.showwarning("Warning", "Please select a collection first!")
            return
        
        file_path = self.file_path_var.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("Warning", "Please select a valid HTML file!")
            return
        
        # Extract handle from selection
        handle = None
        collection_id = None
        try:
            if '(' in selected and ')' in selected:
                handle = selected.split('(')[1].split(')')[0].strip()
            else:
                search_text = selected.lower()
                for collection in self.collections_data:
                    title = collection.get('title', '').lower()
                    coll_handle = collection.get('handle', '').lower()
                    if search_text in title or search_text in coll_handle:
                        handle = collection.get('handle', '')
                        collection_id = collection.get('id', '')
                        break
        except:
            pass
        
        if not handle:
            messagebox.showerror("Error", "Could not find collection handle. Please select from the dropdown.")
            return
        
        # Find collection ID if not found
        if not collection_id:
            for collection in self.collections_data:
                if collection.get('handle', '') == handle:
                    collection_id = collection.get('id', '')
                    break
        
        if not collection_id:
            messagebox.showerror("Error", "Could not find collection ID!")
            return
        
        # Read HTML file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file: {e}")
            return
        
        self.upload_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log(f"Uploading description to collection: {handle}")
        
        def upload():
            try:
                success, error_msg = self.update_collection_description(collection_id, html_content)
                
                if success:
                    self.log(f"✅ Successfully uploaded description!")
                    messagebox.showinfo("Success", "Description uploaded successfully!")
                else:
                    self.log(f"❌ Error: {error_msg}")
                    messagebox.showerror("Error", f"Failed to upload:\n{error_msg}")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.upload_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=upload, daemon=True).start()
    
    def update_collection_description(self, collection_id: str, description_html: str) -> tuple:
        """Update collection description in Shopify
        Returns: (success, error_message)
        """
        if not self.shopify_token or not self.shopify_store:
            return (False, "Shopify credentials not configured")
        
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
            mutation collectionUpdate($input: CollectionInput!) {
              collectionUpdate(input: $input) {
                collection {
                  id
                  title
                  descriptionHtml
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            
            # Convert collection_id to GID format if needed
            original_id = collection_id
            if not collection_id.startswith('gid://'):
                # If it's a numeric ID, convert to GID
                if collection_id.isdigit():
                    collection_id = f"gid://shopify/Collection/{collection_id}"
                else:
                    # Try to extract numeric ID if it's in a different format
                    numbers = re.findall(r'\d+', collection_id)
                    if numbers:
                        collection_id = f"gid://shopify/Collection/{numbers[-1]}"
                    else:
                        return (False, f"Invalid collection ID format: {collection_id}")
            
            self.log(f"  Collection ID: {original_id} -> {collection_id}")
            self.log(f"  Description length: {len(description_html)} characters")
            
            payload = {
                'query': mutation,
                'variables': {
                    'input': {
                        'id': collection_id,
                        'descriptionHtml': description_html
                    }
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            self.log(f"  Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Log full response for debugging
                if 'errors' in result or (result.get('data', {}).get('collectionUpdate', {}).get('userErrors')):
                    self.log(f"  Response: {json.dumps(result, indent=2)[:500]}")
                
                if 'errors' in result:
                    error_msg = '; '.join([e.get('message', str(e)) for e in result['errors']])
                    return (False, f"GraphQL error: {error_msg}")
                
                data = result.get('data', {}).get('collectionUpdate', {})
                user_errors = data.get('userErrors', [])
                
                if user_errors:
                    error_msg = '; '.join([e.get('message', str(e)) for e in user_errors])
                    return (False, f"User errors: {error_msg}")
                
                if data.get('collection'):
                    self.log(f"  ✅ Collection updated: {data['collection'].get('title', 'Unknown')}")
                    return (True, None)
                else:
                    return (False, "No collection returned in response")
            
            error_text = response.text[:200] if response.text else "No error message"
            return (False, f"HTTP {response.status_code}: {error_text}")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"  Exception details: {error_details}")
            return (False, f"Exception: {str(e)}")

def main():
    try:
        root = tk.Tk()
        app = CollectionDescriptionFetcher(root)
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to start application:\n{e}")

if __name__ == "__main__":
    main()

