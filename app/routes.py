from flask import Blueprint, request, jsonify
import json
import requests

from app.services import (
    search_product_with_ai,
    verify_product_match,
    search_product_with_upc,
)
from config import MATCH_CONFIDENCE_THRESHOLD

api_blueprint = Blueprint('api', __name__)


@api_blueprint.route('/api/lookup', methods=['GET'])
def lookup_product():
    try:
        data = request.args

        required_fields = ['productName', 'brandName', 'upc']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Query parameter "{field}" is required'}), 400

        product_name = data.get('productName')
        brand_name = data.get('brandName')
        upc = data.get('upc')
        size = data.get('size', '')
        color = data.get('color', '')
        result = {}

        try:
            result = search_product_with_upc(upc=upc)
            if result is None:
                raise ValueError("UPC search returned no result.")

            verification_data = verify_product_match(
                user_name=product_name,
                user_brand=brand_name,
                upc_name=result['product_name'],
                upc_description=result['description']
            )

            confidence = verification_data.get('match_confidence', 0)

            if confidence >= MATCH_CONFIDENCE_THRESHOLD:
                result['match_confidence'] = confidence
                result['verification_notes'] = f"UPC DB match verified against user input by AI. {verification_data.get('verification_notes', '')}"
                return jsonify(result), 200
            else:
                raise ValueError(f"UPC verification failed (Confidence: {confidence}%). Falling back to full AI search.")

        except Exception as upc_e:
            print(f"UPC Search Failed, falling back to AI: {upc_e}")
            try:
                result = search_product_with_ai(
                    product_name=product_name,
                    brand_name=brand_name,
                    upc=upc,
                    size=size,
                    color=color
                )
            except EnvironmentError as env_e:
                return jsonify({'error': str(env_e)}), 500
            except Exception as ai_e:
                print(f"Gemini Search Failed: {ai_e}")
                return jsonify({'error': f'AI Search failed to find the product: {str(ai_e)}'}), 500

            if not result.get('exact_match', False) or result.get('match_confidence', 0) < MATCH_CONFIDENCE_THRESHOLD:
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
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500


@api_blueprint.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200
