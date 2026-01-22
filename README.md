# Shopify Automation & Analytics Portfolio

This repository contains a collection of Python tools designed to automate complex eCommerce operations, SEO management, and inventory analytics for Shopify stores. 

## 📈 Real-World Business Impact
I used these tools to transform *Reza Gem Collection* from a manual operation to an automated powerhouse.
*   **SEO Domination:** Achieved **Rank #1** on Google for **94 competitive keywords** (like "blue gemstones" & "unakite") and secured **Top 3 positions** for 111+ high-intent search terms.
*   **Sales Performance:** Automation contributed to over **$30,000+ in Total Sales** (Organic / No Ad Spend), including record-breaking single-day performance.
*   **Scale:** Successfully managing **16,000+ SKUs** across digital and physical inventories.
*   **Marketing Automation:** Engineered a data-fetching system to auto-generate email subject lines and content from collection data using **LLM prompts**, reducing campaign creation time by 50%.
*   **Efficiency:** Automated the tracking of **1,000+ keywords**, saving ~20 hours of manual work per week.

## 📂 Project Structure

### 1. `shopify_seo_automation_system.py`
**Description:** A robust object-oriented system for automated SEO optimization.
**Key Features:**
- **AI Integration:** Leverages Google Gemini API to generate professional meta titles and descriptions.
- **GraphQL Mastery:** Uses advanced Shopify GraphQL queries to efficiently read and write metadata.
- **Smart Validation:** Includes logic to validate character counts and content quality before publishing.
- **Error Handling:** Implements comprehensive logging and error protection for production environments.

### 2. `inventory_analytics_reporter.py`
**Description:** A targeted analytics tool for inventory health monitoring.
**Key Features:**
- **Custom Reporting:** Identifies specific stock risk levels (e.g., inventory < 2).
- **Data Aggregation:** Calculates inventory totals and variance.
- **Pagination Handling:** Efficiently processes large catalogs using cursor-based pagination.

### 3. `content_migration_manager.py`
**Description:** An automation script for bulk content migration and management.
**Key Features:**
- **HTML Parsing:** Converts local HTML content into Shopify-compatible blog posts.
- **Duplicate Prevention:** Checks for existing handles to prevent content duplication.
- **REST API:** Demonstrates proficiency with Shopify's REST admin API.

### 4. `offline_to_online_product_matcher.py`
**Description:** A utility to bridge physical inventory with digital systems.
**Key Features:**
- **Fuzzy Matching:** Intellectually matches offline product names with online store entries.
- **Data Reconciliation:** Solves real-world discrepancies between warehouse trays and digital SKUs.

### 5. Desktop GUI Applications (Tkinter)
**Description:** A suite of local desktop applications for managing Shopify data without using the browser.
*   **`gui_internal_link_builder.py`**: A sophisticated SEO tool that automatically builds internal links within product descriptions based on keywords. Features a clear GUI and threading for background processing.
*   **`gui_collection_manager.py`**: A desktop dashboard for fetching and managing collection data locally.
*   **`gui_description_manager.py`**: A comprehensive tool for managing, editing, and bulk-uploading product descriptions via the API.

### 6. `product_image_exporter.py`
**Description:** A high-performance utility for digital asset management.
**Key Features:**
- **GraphQL Pagination:** optimized for fetching large datasets (products + all nested images).
- **Metadata Export:** exports full image metadata (URLs, alt text, dimensions) for analysis.

### 7. `drive_product_importer.py`
**Description:** A complete "Drive-to-Shopify" pipeline.
**Key Features:**
- **Automated Sync:** Reads product data from JSON (Excel export) and automatically fetches matching images from Google Drive.
- **Bulk Creation:** Creates products, variants, and metafields via the Admin API.
- **Smart Grouping:** Logic to group rows into single products based on shared attributes (e.g. Color).

## 🛠️ Tech Stack
- **Python 3.x**
- **Shopify Admin API (GraphQL & REST)**
- **Google Gemini AI API**
- **Pandas / JSON / CSV Data Processing**

---
*Note: Sensitive credentials (API Keys) are managed via localized environment variables and are not included in this repository.*
