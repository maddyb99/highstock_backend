import requests

def search_product_with_upc(upc):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    resp = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}", headers=headers)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("items"):
        raise ValueError("No item found in UPC DB response.")

    item = data.get("items")[0]

    msrp_value = None
    offers = item.get("offers")
    if offers and len(offers) > 0:
        for offer in offers:
            msrp_value = offer.get("price", None)
            if msrp_value:
                break

    result = {
        "description": item.get("description", "No description available."),
        "image_url": item.get("images", []),
        "product_name": item.get("title", "Unknown Product"),
        "source": "UPC Item DB",
        "exact_match": True,
        "match_confidence": 100,
        "msrp": f"${msrp_value}" if msrp_value is not None and msrp_value != "N/A" else "N/A",
        "verification_notes": "Data retrieved directly from UPC Item DB."
    }

    return result
