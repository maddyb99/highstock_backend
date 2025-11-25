from app.models import Product
from app.extensions import db


def search_product_with_db(upc=None, product_name=None, brand=None):
 
    query = Product.query

    if upc:
        query = query.filter_by(upc=upc)
    else:
        # If UPC not provided, try matching by product_name and brand
        if product_name:
            query = query.filter(Product.product_name.ilike(f"%{product_name}%"))
        if brand:
            query = query.filter(Product.brand.ilike(f"%{brand}%"))

    prod = query.first()
    
    if not prod:
        return None

    return prod.to_dict()


def insert_product(product_dict):
    # Accept Pydantic model or dict-like input
    if hasattr(product_dict, "dict") and callable(getattr(product_dict, "dict")):
        product_dict = product_dict.dict()

    # sanitize fields to JSON-serializable primitives
    def sanitize_image_list(img):
        if img is None:
            return []
        if isinstance(img, str):
            return [img]
        try:
            iterable = list(img)
        except Exception:
            return []
        out = []
        for v in iterable:
            try:
                out.append(str(v))
            except Exception:
                continue
        return out

    def to_bool(v):
        return bool(v)

    def to_int_or_none(v):
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    sanitized = {
        "upc": product_dict.get("upc"),
        "brand": product_dict.get("brand"),
        "product_name": product_dict.get("product_name") or product_dict.get("name"),
        "msrp": str(product_dict.get("msrp")) if product_dict.get("msrp") is not None else None,
        "image_url": sanitize_image_list(product_dict.get("image_url")),
        "description": product_dict.get("description"),
        "match_confidence": to_int_or_none(product_dict.get("match_confidence")),
        "source": f"Postgres - {product_dict.get('source')}",
        "exact_match": to_bool(product_dict.get("exact_match")),
        "verification_notes": product_dict.get("verification_notes"),
        "size": product_dict.get("size"),
        "color": product_dict.get("color"),
    }

    try:
        # Create new
        new = Product(
            upc=sanitized["upc"],
            brand=sanitized["brand"],
            product_name=sanitized["product_name"],
            msrp=sanitized["msrp"],
            image_url=sanitized["image_url"],
            description=sanitized["description"],
            match_confidence=sanitized["match_confidence"],
            source=sanitized["source"],
            exact_match=sanitized["exact_match"],
            verification_notes=sanitized["verification_notes"],
            size=sanitized["size"],
            color=sanitized["color"],
        )

        db.session.add(new)
        db.session.commit()
        return new.to_dict()
    except Exception as e:
        print(f"Upsert Failed: {e}")
        db.session.rollback()
        raise
