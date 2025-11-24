from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import os
import json
import re
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

def extract_json_from_response(text):
    """Extract JSON from Claude's response, handling markdown code blocks"""
    # Try to find JSON in markdown code blocks
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # Try to find raw JSON object
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return text

def search_product_with_ai(product_name, brand_name, upc, size=None, color=None):

    # Initialize Claude API client
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )

    """
    Use Claude with web search to find exact product match
    """
    # Build search query
    search_query = f"{brand_name} {product_name}"
    if size:
        search_query += f" {size}"
    if color:
        search_query += f" {color}"
    search_query += f" UPC {upc}"
    
    prompt = f"""You are a product data enrichment assistant. Find the EXACT product match for:

Product Name: {product_name}
Brand: {brand_name}
UPC: {upc}
{f"Size: {size}" if size else ""}
{f"Color/Shade: {color}" if color else ""}

CRITICAL REQUIREMENTS:
1. Find the EXACT product match - same brand, same size/volume, same color/shade
2. Do NOT return similar or alternative products
3. Verify the UPC matches if possible
4. Find the official MSRP (manufacturer's suggested retail price)
5. Find a high-quality product image URL
6. Provide a brief product description (2-3 sentences)

Search multiple retailer websites (Sephora, Ulta, brand's official website, Amazon, etc.) to verify the information.

Return ONLY a JSON object with this structure (no markdown, no explanation):
{{
    "product_name": "Full product name with brand, size, and color",
    "msrp": "$XX.XX",
    "image_url": ["https://...","https://..."],
    "description": "Brief product description",
    "match_confidence": "your confidence with the result as integer",
    "source": "website name",
    "exact_match": true,
    "verification_notes": "Brief notes on match verification"
}}

If you cannot find an exact match, set exact_match to false and match_confidence below 70."""
    print(prompt)
    try:
        # Use Claude with web search tool
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search"
            }],
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        # Extract response text from content blocks
        response_text = ""
        for block in message.content:
            if hasattr(block, 'text'):
                response_text += block.text
        
        # Extract and parse JSON
        json_str = extract_json_from_response(response_text)
        result = json.loads(json_str)
        
        return result
        
    except Exception as e:
        print(f"Error in AI search: {str(e)}")
        raise

def search_product_with_upc(upc):
    headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip,deflate',
            }
    resp = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if data.get("items",0)==0:
        raise ValueError("items cannot be 0")
    f = open("resp.json","w")
    json.dump(data,f)
    item = data.get("items")[0]

    result = {
        "description": item["description"],
        "image_url": item["images"],
        "product_name": item["title"],
        "source": "UPC Item DB",
        "exact_match": True,
        "match_confidence": 100,
        "msrp": item.get("offers",[])[0].get("price",None)
    }
    print("**********UPC RESULT********")
    print(result)

    return result
        

@app.route('/api/lookup', methods=['GET'])
def lookup_product():
    """
    Main API endpoint for product lookup
    """
    try:
        data = request.args
        
        # Validate required fields
        required_fields = ['productName', 'brandName', 'upc']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Extract data
        product_name = data['productName']
        brand_name = data['brandName']
        upc = data['upc']
        size = data.get('size', '')
        color = data.get('color', '')
        result = {}
        try:
            #search using UPC
            result = search_product_with_upc(upc=upc)
            # result = None
            if result is None:
                raise ValueError("result cannot be null")
        except Exception as e:
            print(e)
            # Search using AI
            result = search_product_with_ai(
                product_name=product_name,
                brand_name=brand_name,
                upc=upc,
                size=size,
                color=color
            )
            print(result)
            # Check if exact match found
            if not result.get('exact_match', False) or result.get('match_confidence', 0) < 70:
                return jsonify({
                    'error': 'Could not find exact product match. Please verify the product details.',
                    'partial_result': result
                }), 404
        
        return jsonify(result), 200
        
    except json.JSONDecodeError as e:
        return jsonify({'error': 'Invalid JSON response from AI'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
