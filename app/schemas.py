from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


class LookupParams(BaseModel):
    productName: str
    brandName: str
    upc: str
    size: Optional[str] = None
    color: Optional[str] = None


class ProductResult(BaseModel):
    product_name: str
    msrp: Optional[str] = None
    image_url: List[HttpUrl] = Field(default_factory=list)
    description: Optional[str] = None
    match_confidence: int = 0
    source: Optional[str] = None
    exact_match: bool = False
    verification_notes: Optional[str] = None


class VerificationResult(BaseModel):
    match_confidence: int
    verification_notes: Optional[str] = None
