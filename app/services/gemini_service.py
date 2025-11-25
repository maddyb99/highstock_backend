import os
import json
import requests
import time
import re

from config import GEMINI_API_URL, MAX_RETRIES


def extract_json_from_response(text):
    json_match = re.search(r'```json\s*(\{.*?})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1].strip()

    raise ValueError("Could not extract a valid JSON object from the AI response.")


def call_gemini_api(prompt, use_search_tools=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not set.")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }

    if use_search_tools:
        payload["tools"] = [{"google_search": {}}]

    full_url = f"{GEMINI_API_URL}?key={api_key}"

    for i in range(MAX_RETRIES):
        try:
            response = requests.post(full_url, headers={'Content-Type': 'application/json'}, json=payload)
            response.raise_for_status()
            data = response.json()

            if not data.get("candidates") or not data["candidates"][0].get("content"):
                raise ValueError(f"Gemini API response content missing or blocked. Data: {data}")

            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            json_str = extract_json_from_response(raw_text)
            return json.loads(json_str)

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP Error: {http_err.response.status_code}. Response: {http_err.response.text}")
            if i < MAX_RETRIES - 1:
                wait_time = 2 ** i
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
        except (ValueError, json.JSONDecodeError, requests.exceptions.RequestException) as e:
            if i < MAX_RETRIES - 1:
                wait_time = 2 ** i
                print(f"Gemini API request failed ({type(e).__name__}). Retrying in {wait_time}s. Error: {e}")
                time.sleep(wait_time)
            else:
                raise


PRODUCT_SCHEMA_PROMPT = """
{
    "product_name": "Full product name with brand, size, and color",
    "msrp": "$XX.XX",
    "image_url": ["https://...", "https://..."],
    "description": "Brief product description",
    "match_confidence": 0,
    "source": "website name",
    "exact_match": true,
    "verification_notes": "Brief notes on match verification"
}
"""

VERIFICATION_SCHEMA_PROMPT = """
{
    "match_confidence": 0,
    "verification_notes": "Brief comparison notes (e.g., 'Brand names match, product names are similar.')"
}
"""


def search_product_with_ai(product_name, brand_name, upc, size=None, color=None):
    prompt = f"""You are a world-class product data enrichment assistant. Your task is to find the EXACT match for the following product details.

Input Details:
Product Name: {product_name}
Brand: {brand_name}
UPC: {upc}
{f"Size: {size}" if size else ""}
{f"Color/Shade: {color}" if color else ""}

CRITICAL REQUIREMENTS:
1. Find the EXACT product match - same brand, same size/volume, and same color/shade if specified.
2. Do NOT return similar or alternative products.
3. Verify the UPC matches the product found through web search.
4. Find the official MSRP (manufacturer's suggested retail price).
5. Find at least one high-quality product image URL.
6. Provide a brief, concise product description (max 3 sentences).
7. If an exact match is not found or the UPC verification fails, set 'exact_match' to false and 'match_confidence' below 70.

Return the result STRICTLY as a single JSON object matching the structure below. Wrap the JSON in a markdown code block (```json...```). Do not include any introductory or explanatory text outside the JSON block.

JSON Structure MUST match this:
{PRODUCT_SCHEMA_PROMPT}"""

    return call_gemini_api(prompt, use_search_tools=True)


def verify_product_match(user_name, user_brand, upc_name, upc_description):
    prompt = f"""You are a product data matching expert. Compare the 'User Input' against the 'UPC Database Result'.

USER INPUT:
Product Name: {user_name}
Brand Name: {user_brand}

UPC DATABASE RESULT:
Product Name: {upc_name}
Description: {upc_description}

Your task is to determine the confidence level (0-100) that the UPC database result is an exact match for the user's intended product, based *only* on the provided names.

Return the result STRICTLY as a single JSON object matching the structure below. Wrap the JSON in a markdown code block (```json...```). Do not include any introductory or explanatory text outside the JSON block.

JSON Structure MUST match this:
{VERIFICATION_SCHEMA_PROMPT}"""

    return call_gemini_api(prompt, use_search_tools=False)
