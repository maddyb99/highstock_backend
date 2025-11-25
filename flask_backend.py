from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import requests
import time # Import for exponential backoff
import re # Import for extracting JSON from markdown

app = Flask(__name__)
CORS(app)  

# Define the JSON schema (used in the prompt, but not in the API config due to the tool conflict)
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

# The Gemini API uses the GEMINI_API_KEY environment variable
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
MAX_RETRIES = 5

def extract_json_from_response(text):
    """Extract JSON from the model's text response, handling markdown code blocks."""
    # Pattern to find JSON enclosed in ```json...```
    json_match = re.search(r'```json\s*(\{.*?})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # Fallback: attempt to find a standalone JSON object
    try:
        # Simple attempt to load the entire text if it's already pure JSON
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Last resort: find the first and last brace to extract what looks like JSON
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1].strip()
            
    raise ValueError("Could not extract a valid JSON object from the AI response.")


def search_product_with_ai(product_name, brand_name, upc, size=None, color=None):
    """
    Use Gemini with Google Search grounding to find exact product match.
    Note: Structured JSON output (responseSchema) is disabled to allow for tool use.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not set.")

    # Build detailed prompt for the AI
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

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]  # Enable Google Search grounding
        # responseSchema is REMOVED to support tool use.
    }
    
    # Construct the full URL with the API key
    full_url = f"{GEMINI_API_URL}?key={api_key}"

    # Implement exponential backoff for API calls
    for i in range(MAX_RETRIES):
        try:
            response = requests.post(full_url, headers={'Content-Type': 'application/json'}, json=payload)
            
            # Raise HTTPError for bad responses (4xx or 5xx)
            response.raise_for_status() 
            
            data = response.json()
            
            if not data.get("candidates") or not data["candidates"][0].get("content"):
                raise ValueError(f"Gemini API response content missing or blocked. Data: {data}")

            # Extract the raw text from the response
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Extract and parse the JSON from the raw text
            json_str = extract_json_from_response(raw_text)
            
            # The structured output should be pure JSON, so we can directly parse it
            result = json.loads(json_str)
            return result
        
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP Error: {http_err.response.status_code}. Response: {http_err.response.text}")
            if i < MAX_RETRIES - 1:
                wait_time = 2 ** i
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Gemini API failed after {MAX_RETRIES} attempts. Last HTTP error: {http_err}")
                raise
        except (ValueError, json.JSONDecodeError, requests.exceptions.RequestException) as e:
            if i < MAX_RETRIES - 1:
                wait_time = 2 ** i
                print(f"Gemini API request failed ({type(e).__name__}). Retrying in {wait_time}s. Error: {e}")
                time.sleep(wait_time)
            else:
                print(f"Gemini API failed after {MAX_RETRIES} attempts. Last error: {e}")
                raise

def search_product_with_upc(upc):
    # Added User-Agent to prevent 403 errors from the external API
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip,deflate',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Using the trial endpoint
    resp = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}", headers=headers)
    resp.raise_for_status() # Raise exception for 4xx or 5xx status codes
    data = resp.json()
    
    if not data.get("items"):
        # If the 'items' key is missing or empty list, treat as no result found
        raise ValueError("No item found in UPC DB response.")
        
    item = data.get("items")[0]

    # Clean up MSRP data, some APIs return price in a sub-object
    msrp_value = None
    offers = item.get("offers")
    if offers and len(offers) > 0:
        for offer in offers:
            msrp_value = offer.get("price", None)
            if msrp_value:
                break
        
    # Format the result to match the AI search structure
    result = {
        "description": item.get("description", "No description available."),
        # UPC DB returns a list of image URLs
        "image_url": item.get("images", []),
        "product_name": item.get("title", "Unknown Product"),
        "source": "UPC Item DB",
        "exact_match": True,
        "match_confidence": 100,
        "msrp": f"${msrp_value}" if msrp_value is not None and msrp_value != "N/A" else "N/A",
        "verification_notes": "Data retrieved directly from UPC Item DB."
    }

    return result
        

@app.route('/api/lookup', methods=['GET'])
def lookup_product():
    """
    Main API endpoint for product lookup using GET query parameters
    """
    try:
        # Use request.args for GET parameters (query string)
        data = request.args
        
        # Validate required fields
        required_fields = ['productName', 'brandName', 'upc']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Query parameter "{field}" is required'}), 400
        
        # Extract data
        product_name = data.get('productName')
        brand_name = data.get('brandName')
        upc = data.get('upc')
        size = data.get('size', '')
        color = data.get('color', '')
        result = {}
        
        # --- Search Logic ---
        try:
            # 1. Search using UPC
            result = search_product_with_upc(upc=upc)
            if result is None:
                raise ValueError("UPC search returned no result.")
        except Exception as upc_e:
            print(f"UPC Search Failed, falling back to AI: {upc_e}")
            
            # 2. Search using AI (Fallback)
            try:
                result = search_product_with_ai(
                    product_name=product_name,
                    brand_name=brand_name,
                    upc=upc,
                    size=size,
                    color=color
                )
            except EnvironmentError as env_e:
                # Handle missing API key specifically
                return jsonify({'error': str(env_e)}), 500
            except Exception as ai_e:
                print(f"Gemini Search Failed: {ai_e}")
                return jsonify({'error': f'AI Search failed to find the product: {str(ai_e)}'}), 500

            # Check if AI result is good enough
            if not result.get('exact_match', False) or result.get('match_confidence', 0) < 70:
                # Return partial result with 404
                return jsonify({
                    'error': 'Could not find exact product match. Please verify the product details.',
                    'partial_result': result
                }), 404
        
        return jsonify(result), 200
        
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON structure from API response (Parsing Error): {str(e)}'}), 500
    except requests.exceptions.HTTPError as e:
        return jsonify({'error': f'External API Error (UPC DB or Gemini): {str(e)}'}), 500
    except Exception as e:
        # Generic catch-all error
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # Running in debug mode for local testing
    app.run(debug=True, host='0.0.0.0', port=5000)