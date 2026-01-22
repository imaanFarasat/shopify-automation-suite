import json
import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv


load_dotenv()


def setup_shopify() -> Dict[str, str]:
    """
    Setup Shopify API connection details from environment variables.

    Required env vars:
      - SHOPIFY_SHOP_NAME         e.g. rezagemcollection (with or without .myshopify.com)
      - SHOPIFY_API_PASSWORD      Admin API access token
    """
    shop_name = os.getenv("SHOPIFY_SHOP_NAME")
    api_password = os.getenv("SHOPIFY_API_PASSWORD")

    if not all([shop_name, api_password]):
        raise ValueError(
            "Missing required environment variables: SHOPIFY_SHOP_NAME or SHOPIFY_API_PASSWORD"
        )

    if shop_name.endswith(".myshopify.com"):
        shop_domain = shop_name
    else:
        shop_domain = f"{shop_name}.myshopify.com"

    base_url = f"https://{shop_domain}/admin/api/2024-01"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Shopify-Access-Token": api_password,
    }

    return {"base_url": base_url, "headers": headers}


def make_graphql_request(
    base_url: str, headers: Dict[str, str], query: str, variables: Optional[Dict] = None
) -> Dict:
    """Make a GraphQL request to Shopify."""
    url = f"{base_url}/graphql.json"
    payload = {"query": query, "variables": variables or {}}

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
            verify=True,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Error details: {error_detail}")
            except Exception:
                print(f"Response text: {e.response.text}")
        return {"errors": [{"message": str(e)}]}


def load_earrings_tray1() -> List[Dict]:
    """Load all rows from EarringsTray1.json."""
    with open("EarringsTray1.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("EarringsTray1.json is expected to be a JSON array.")

    return data


def find_product_by_title(
    base_url: str, headers: Dict[str, str], title: str
) -> Optional[Dict]:
    """
    Find a Shopify product by exact title, preferring the newest one.

    Returns a dict with id, numeric_id, title, handle if found, else None.
    """
    query_str = """
    query ($first: Int!, $query: String!) {
      products(first: $first, query: $query, sortKey: CREATED_AT, reverse: true) {
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

    variables = {
        "first": 5,
        "query": f'title:"{title}"',
    }

    data = make_graphql_request(base_url, headers, query_str, variables)
    if "errors" in data:
        print(f"  ⚠ GraphQL error while searching for '{title}': {data['errors']}")
        return None

    edges = (
        data.get("data", {})
        .get("products", {})
        .get("edges", [])
        or []
    )

    for edge in edges:
        node = edge.get("node") or {}
        if (node.get("title") or "").strip() == title.strip():
            gid = node.get("id")
            numeric_id = None
            if gid and gid.startswith("gid://shopify/Product/"):
                numeric_id = gid.split("/")[-1]

            return {
                "id": gid,
                "numeric_id": numeric_id,
                "title": node.get("title") or "",
                "handle": node.get("handle") or "",
            }

    return None


def main() -> None:
    """
    Match all distinct titles in EarringsTray1.json to Shopify products
    and save their IDs into a JSON file:

      earrings_tray1_shopify_ids.json
    """
    rows = load_earrings_tray1()

    conn = setup_shopify()
    base_url = conn["base_url"]
    headers = conn["headers"]

    seen_titles = set()
    results: List[Dict] = []

    for row in rows:
        title = (row.get("Title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        photo_folder = (row.get("Photo Folder") or "").strip()
        gemstone_name = (row.get("Gemstone Name") or "").strip()

        print(f"Searching Shopify for title: '{title}'")
        match = find_product_by_title(base_url, headers, title)

        entry: Dict = {
            "title": title,
            "photo_folder": photo_folder,
            "gemstone_name": gemstone_name,
        }

        if match:
            print(
                f"  ✓ Found: {match['title']} "
                f"(id: {match['numeric_id'] or match['id']}, handle: {match['handle']})"
            )
            entry.update(
                {
                    "shopify_id": match["id"],
                    "shopify_numeric_id": match["numeric_id"],
                    "shopify_handle": match["handle"],
                }
            )
        else:
            print("  ✗ No exact match found.")
            entry.update(
                {
                    "shopify_id": None,
                    "shopify_numeric_id": None,
                    "shopify_handle": None,
                }
            )

        results.append(entry)

    # Save to JSON
    out_filename = "earrings_tray1_shopify_ids.json"
    with open(out_filename, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_titles": len(results),
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n✅ Saved Shopify ID matches to: {out_filename}")


if __name__ == "__main__":
    main()
