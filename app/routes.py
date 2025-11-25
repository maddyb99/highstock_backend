from flask import Blueprint, request, jsonify, Response
import json
import requests

from pydantic import ValidationError

from app.services import (
    search_product_with_ai,
    verify_product_match,
    search_product_with_upc,
)
from app.schemas import LookupParams, ProductResult, VerificationResult
from config import MATCH_CONFIDENCE_THRESHOLD

api_blueprint = Blueprint('api', __name__)


@api_blueprint.route('/api/lookup', methods=['GET'])
def lookup_product():
    try:
        args = request.args.to_dict(flat=True)

        try:
            params = LookupParams(**args)
        except ValidationError as ve:
            return jsonify({'error': 'Invalid query parameters', 'details': ve.errors()}), 400

        # Try UPC lookup first
        try:
            upc_result = search_product_with_upc(upc=params.upc)
            
            if upc_result is None:
                raise ValueError("UPC search returned no result.")

            verification_data = verify_product_match(
                user_name=params.productName,
                user_brand=params.brandName,
                upc_name=upc_result.get('product_name', ''),
                upc_description=upc_result.get('description', '')
            )

            # Parse verification result
            try:
                verification = VerificationResult.parse_obj(verification_data)
            except Exception:
                verification = VerificationResult(match_confidence=int(verification_data.get('match_confidence', 0)), verification_notes=verification_data.get('verification_notes', None))
            
            if verification.match_confidence >= MATCH_CONFIDENCE_THRESHOLD:
                # Return the UPC result with updated confidence
                product = ProductResult.parse_obj({**upc_result, 'match_confidence': verification.match_confidence})
                # Return a JSON string produced by pydantic to ensure HttpUrl and other types are serialized
                return Response(product.json(), mimetype='application/json'), 200
            else:
                raise ValueError(f"UPC verification failed (Confidence: {verification.match_confidence}%). Falling back to full AI search.")

        except Exception as upc_e:
            print(f"UPC Search Failed, falling back to AI: {upc_e}")

            # Fallback to AI search
            try:
                ai_result = search_product_with_ai(
                    product_name=params.productName,
                    brand_name=params.brandName,
                    upc=params.upc,
                    size=params.size,
                    color=params.color
                )
            except EnvironmentError as env_e:
                return jsonify({'error': str(env_e)}), 500
            except Exception as ai_e:
                print(f"Gemini Search Failed: {ai_e}")
                return jsonify({'error': f'AI Search failed to find the product: {str(ai_e)}'}), 500

            try:
                product = ProductResult.parse_obj(ai_result)
            except Exception:
                # If parsing fails, try to coerce basic fields
                product = ProductResult(
                    product_name=ai_result.get('product_name', 'Unknown Product'),
                    msrp=ai_result.get('msrp'),
                    image_url=ai_result.get('image_url', []),
                    description=ai_result.get('description'),
                    match_confidence=int(ai_result.get('match_confidence', 0)),
                    source=ai_result.get('source'),
                    exact_match=bool(ai_result.get('exact_match', False)),
                    verification_notes=ai_result.get('verification_notes')
                )

            if not product.exact_match or product.match_confidence < MATCH_CONFIDENCE_THRESHOLD:
                # Convert the pydantic model to native types for the partial result
                partial = json.loads(product.json())
                return jsonify({
                    'error': 'Could not find exact product match. Please verify the product details.',
                    'partial_result': partial
                }), 404

            return Response(product.json(), mimetype='application/json'), 200

    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON structure from API response (Parsing Error): {str(e)}'}), 500
    except requests.exceptions.HTTPError as e:
        return jsonify({'error': f'External API Error (UPC DB or Gemini): {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500



@api_blueprint.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200
