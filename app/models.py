from .extensions import db

class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = {'schema': 'products'}

    id = db.Column(db.Integer, primary_key=True)
    upc = db.Column(db.String, index=True, nullable=False)
    brand = db.Column(db.String, nullable=False)
    product_name = db.Column(db.String, nullable=False)
    msrp = db.Column(db.String, nullable=True)
    image_url = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=True)
    match_confidence = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String, nullable=True)
    exact_match = db.Column(db.Boolean, default=False)
    verification_notes = db.Column(db.Text, nullable=True)
    size = db.Column(db.String, nullable=True)
    color = db.Column(db.String, nullable=True)

    def to_dict(self):
        return {
            'product_name': self.product_name,
            'msrp': self.msrp,
            'image_url': self.image_url or [],
            'description': self.description,
            'match_confidence': int(self.match_confidence) if self.match_confidence is not None else 0,
            'source': self.source,
            'exact_match': bool(self.exact_match),
            'verification_notes': self.verification_notes,
            'upc': self.upc,
            'brand': self.brand,
            'size': self.size,
            'color': self.color,
        }
