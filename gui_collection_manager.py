import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
import threading
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables
load_dotenv()

class CollectionFetcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Collection Fetcher")
        self.root.geometry("700x600")
        self.root.configure(bg="#f5f5f5")
        
        # Load Shopify credentials
        self.shopify_store = os.getenv('SHOPIFY_SHOP_NAME', '').strip()
        self.shopify_token = os.getenv('SHOPIFY_API_PASSWORD', '').strip()
        
        # JSON file path
        self.json_file = os.path.join(os.path.dirname(__file__), 'collections.json')
        
        self.setup_ui()
        self.load_existing_collections()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_frame = tk.Frame(self.root, bg="#f5f5f5", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Label(
            main_frame,
            text="📦 Collection Fetcher",
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
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg="#f5f5f5")
        button_frame.pack(pady=20)
        
        self.fetch_btn = tk.Button(
            button_frame,
            text="Fetch All Collections",
            command=self.fetch_all_collections,
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
            text="Update (New Only)",
            command=self.update_collections,
            bg="#2ecc71",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            width=20
        )
        self.update_btn.pack(side=tk.LEFT, padx=10)
        
        # Stats
        self.stats_label = tk.Label(
            main_frame,
            text="Collections: 0",
            font=("Arial", 11),
            bg="#f5f5f5",
            fg="#7f8c8d"
        )
        self.stats_label.pack(pady=10)
        
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
        
        self.log("Collection Fetcher Ready")
    
    def log(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def load_existing_collections(self):
        """Load existing collections from JSON file"""
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    collections = json.load(f)
                self.stats_label.config(text=f"Collections: {len(collections)}")
                self.log(f"Loaded {len(collections)} existing collections")
            except:
                self.log("Could not load existing collections")
        else:
            self.log("No existing collections file found")
    
    def fetch_collections_from_shopify(self) -> List[Dict]:
        """Fetch all collections from Shopify"""
        if not self.shopify_token or not self.shopify_store:
            self.log("⚠️ Shopify credentials not configured")
            return []
        
        shop = self.shopify_store
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        
        collections = []
        cursor = None
        has_next = True
        
        try:
            url = f"https://{shop}/admin/api/2024-01/graphql.json"
            headers = {
                'X-Shopify-Access-Token': self.shopify_token,
                'Content-Type': 'application/json'
            }
            
            self.log(f"Connecting to: {shop}")
            
            while has_next:
                query = """
                query getCollections($first: Int!, $after: String) {
                  collections(first: $first, after: $after) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    edges {
                      node {
                        id
                        title
                        handle
                      }
                    }
                  }
                }
                """
                
                if cursor:
                    variables = {"first": 250, "after": cursor}
                else:
                    variables = {"first": 250}
                
                response = requests.post(
                    url,
                    json={'query': query, 'variables': variables},
                    headers=headers,
                    timeout=30
                )
                
                self.log(f"Response status: {response.status_code}")
                
                if response.status_code != 200:
                    self.log(f"❌ HTTP Error {response.status_code}: {response.text[:200]}")
                    break
                
                result = response.json()
                
                # Check for GraphQL errors
                if 'errors' in result:
                    self.log(f"❌ GraphQL Errors: {result['errors']}")
                    break
                
                # Check if data exists
                if 'data' not in result:
                    self.log(f"❌ No data in response: {result}")
                    break
                
                data = result.get('data', {})
                if 'collections' not in data:
                    self.log(f"❌ No collections in data: {data}")
                    break
                
                collections_data = data.get('collections', {})
                edges = collections_data.get('edges', [])
                
                self.log(f"Found {len(edges)} collections in this page")
                
                for edge in edges:
                    node = edge.get('node', {})
                    collections.append({
                        'id': node.get('id', ''),
                        'title': node.get('title', ''),
                        'handle': node.get('handle', '')
                    })
                
                page_info = collections_data.get('pageInfo', {})
                has_next = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')
                
                self.log(f"Total fetched so far: {len(collections)}")
                
                if not has_next:
                    break
            
            return collections
        except Exception as e:
            import traceback
            self.log(f"❌ Error fetching collections: {e}")
            self.log(traceback.format_exc())
            return []
    
    def fetch_all_collections(self):
        """Fetch all collections and save to JSON"""
        self.fetch_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log("Fetching all collections from Shopify...")
        
        def fetch():
            try:
                collections = self.fetch_collections_from_shopify()
                
                if not collections:
                    self.log("No collections found or error occurred")
                    messagebox.showwarning("Warning", "Could not fetch collections. Check your credentials.")
                    return
                
                # Save to JSON
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump(collections, f, indent=2, ensure_ascii=False)
                
                self.log(f"\n✅ Successfully fetched {len(collections)} collections")
                self.log(f"Saved to: {self.json_file}")
                self.stats_label.config(text=f"Collections: {len(collections)}")
                
                messagebox.showinfo("Success", f"Fetched {len(collections)} collections!")
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=fetch, daemon=True).start()
    
    def update_collections(self):
        """Update collections - only add new ones"""
        self.update_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.log("Updating collections (checking for new ones)...")
        
        def update():
            try:
                # Load existing collections
                existing = {}
                if os.path.exists(self.json_file):
                    with open(self.json_file, 'r', encoding='utf-8') as f:
                        existing_list = json.load(f)
                        existing = {c['handle']: c for c in existing_list}
                    self.log(f"Loaded {len(existing)} existing collections")
                
                # Fetch all from Shopify
                all_collections = self.fetch_collections_from_shopify()
                
                if not all_collections:
                    self.log("No collections found or error occurred")
                    messagebox.showwarning("Warning", "Could not fetch collections.")
                    return
                
                # Find new collections
                new_collections = []
                for coll in all_collections:
                    if coll['handle'] not in existing:
                        new_collections.append(coll)
                        self.log(f"New: {coll['title']} ({coll['handle']})")
                
                if not new_collections:
                    self.log("\n✅ No new collections found - everything is up to date!")
                    messagebox.showinfo("Update Complete", "No new collections found!")
                    return
                
                # Add new collections to existing
                updated = list(existing.values()) + new_collections
                
                # Save updated list
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump(updated, f, indent=2, ensure_ascii=False)
                
                self.log(f"\n✅ Added {len(new_collections)} new collection(s)")
                self.log(f"Total collections: {len(updated)}")
                self.stats_label.config(text=f"Collections: {len(updated)}")
                
                messagebox.showinfo("Update Complete", f"Added {len(new_collections)} new collection(s)!")
            except Exception as e:
                self.log(f"Error: {e}")
                messagebox.showerror("Error", str(e))
            finally:
                self.update_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=update, daemon=True).start()

def main():
    root = tk.Tk()
    app = CollectionFetcherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

