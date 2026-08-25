"""
Product Matching Service
Matches products across stores using model numbers, brand extraction, 
URL identifiers, and fuzzy title comparison.
Uses only stdlib — no external dependencies.
"""

import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger("product_matcher")

# Common brand names for extraction
KNOWN_BRANDS = [
    "samsung", "apple", "sony", "lg", "oneplus", "xiaomi", "realme", "oppo",
    "vivo", "motorola", "nokia", "google", "asus", "lenovo", "hp", "dell",
    "acer", "msi", "bose", "jbl", "sennheiser", "boat", "nike", "adidas",
    "puma", "reebok", "levi's", "levis", "zara", "h&m", "mango", "peter england",
    "van heusen", "raymond", "allen solly", "louis philippe", "us polo",
    "woodland", "red tape", "bata", "sparx", "campus", "wildcraft",
    "boAt", "noise", "fire-boltt", "fossil", "titan", "casio", "fastrack",
    "whirlpool", "haier", "godrej", "ifb", "voltas", "daikin", "philips",
    "prestige", "bajaj", "havells", "crompton", "orient", "usha",
]

# Common stop words to remove during title comparison
STOP_WORDS = {
    "the", "a", "an", "and", "or", "in", "on", "for", "with", "by",
    "from", "to", "of", "is", "it", "its", "this", "that", "new", "buy",
    "online", "india", "best", "price", "latest", "original", "genuine",
    "free", "delivery", "shipping", "offer", "sale", "discount", "deal",
    "pack", "combo", "set", "edition", "version", "model", "series",
    "-", "|", "/", "(", ")", "[", "]", ",", ".", ":", ";",
}


def extract_model_number(title: str) -> Optional[str]:
    """
    Extracts a model/part number from a product title.
    Looks for patterns like: WH-1000XM5, SM-S911B, iPhone 15, RTX 4090, etc.
    """
    if not title:
        return None
    
    # Pattern 1: alphanumeric model codes with dashes/dots (WH-1000XM5, SM-S911B, etc.)
    model_patterns = [
        r'\b([A-Z]{1,4}[-\s]?\d{2,5}[A-Z]{0,3}\d{0,2})\b',  # WH-1000XM5, SM-S911B
        r'\b([A-Z]\d{2,}[A-Z]?\d*)\b',                         # A54, S23, M34
        r'\b(iPhone\s*\d+\s*(?:Pro\s*Max|Pro|Plus|Mini)?)\b',   # iPhone 15 Pro Max
        r'\b(Galaxy\s*[A-Z]\d+\s*(?:Ultra|Plus|FE)?)\b',        # Galaxy S24 Ultra
        r'\b(Pixel\s*\d+\s*(?:Pro|a)?)\b',                      # Pixel 8 Pro
        r'\b(MacBook\s*(?:Air|Pro)\s*(?:M\d+)?)\b',             # MacBook Pro M3
        r'\b(RTX\s*\d{4}\s*(?:Ti|Super)?)\b',                   # RTX 4090
        r'\b(RX\s*\d{4}\s*(?:XT|XTX)?)\b',                     # RX 7900 XTX
    ]
    
    title_upper = title.upper() if title else ""
    
    for pattern in model_patterns:
        match = re.search(pattern, title_upper if pattern.startswith(r'\b([A-Z]') else title, re.IGNORECASE)
        if match:
            model = match.group(1).strip()
            # Normalize: remove spaces around dashes, collapse spaces
            model = re.sub(r'\s*-\s*', '-', model)
            model = re.sub(r'\s+', ' ', model)
            return model.upper()
    
    return None


def extract_brand(title: str) -> Optional[str]:
    """Extract brand name from product title."""
    if not title:
        return None
    
    title_lower = title.lower().strip()
    
    for brand in KNOWN_BRANDS:
        brand_lower = brand.lower()
        # Check if brand appears at start of title or as a word boundary
        if title_lower.startswith(brand_lower + " ") or title_lower.startswith(brand_lower + "-"):
            return brand_lower
        if re.search(r'\b' + re.escape(brand_lower) + r'\b', title_lower):
            return brand_lower
    
    return None


def extract_url_identifier(url: str) -> Optional[str]:
    """Extract product-specific identifier from URL."""
    if not url:
        return None
    
    url_lower = url.lower()
    
    # Amazon ASIN: /dp/B0XXXXXXXX or /gp/product/B0XXXXXXXX
    asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url, re.IGNORECASE)
    if asin_match:
        return f"ASIN:{asin_match.group(1).upper()}"
    
    # Flipkart product ID: /p/itm{id}
    fk_match = re.search(r'/p/(itm[a-z0-9]+)', url_lower)
    if fk_match:
        return f"FK:{fk_match.group(1)}"
    
    # Myntra product ID: /buy/{brand}/{name}/{id}/buy or /{id}/buy
    myntra_match = re.search(r'/(\d{6,})/buy', url_lower)
    if not myntra_match:
        myntra_match = re.search(r'/(\d{6,})(?:/|$)', url_lower)
    if myntra_match:
        return f"MYNTRA:{myntra_match.group(1)}"
    
    return None


def normalize_title(title: str) -> str:
    """Normalize a product title for comparison by removing noise."""
    if not title:
        return ""
    
    # Lowercase
    t = title.lower().strip()
    
    # Remove common store-specific suffixes
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t)  # Remove parenthetical info
    t = re.sub(r'\s*\[.*?\]\s*', ' ', t)  # Remove bracket info
    t = re.sub(r'\b(amazon|flipkart|myntra)\b', '', t, flags=re.IGNORECASE)
    
    # Remove special characters but keep alphanumeric and spaces
    t = re.sub(r'[^\w\s-]', ' ', t)
    
    # Remove stop words
    tokens = t.split()
    tokens = [tok for tok in tokens if tok not in STOP_WORDS and len(tok) > 1]
    
    return ' '.join(tokens)


def calculate_title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two normalized titles."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # SequenceMatcher ratio
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Also check token overlap (Jaccard similarity)
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    
    if not tokens1 or not tokens2:
        return ratio
    
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard = len(intersection) / len(union) if union else 0.0
    
    # Weighted combination
    return 0.6 * ratio + 0.4 * jaccard


def match_products(
    source_product: Dict,
    candidate_products: List[Dict],
    min_confidence: float = 0.6
) -> List[Dict]:
    """
    Match a source product against a list of candidate products.
    
    Each product dict should have keys: 
    - id, name, links (list of dicts with 'url', 'website', 'current_price')
    
    Returns list of matches with confidence scores.
    """
    if not source_product or not candidate_products:
        return []
    
    source_name = source_product.get("name", "")
    source_model = extract_model_number(source_name)
    source_brand = extract_brand(source_name)
    
    # Get URL identifiers from source links
    source_url_ids = set()
    source_websites = set()
    for link in source_product.get("links", []):
        uid = extract_url_identifier(link.get("url", ""))
        if uid:
            source_url_ids.add(uid)
        source_websites.add(link.get("website", "").lower())
    
    matches = []
    
    for candidate in candidate_products:
        if candidate.get("id") == source_product.get("id"):
            continue  # Skip self-match
        
        cand_name = candidate.get("name", "")
        cand_model = extract_model_number(cand_name)
        cand_brand = extract_brand(cand_name)
        
        # Get candidate URL identifiers and websites
        cand_url_ids = set()
        cand_websites = set()
        for link in candidate.get("links", []):
            uid = extract_url_identifier(link.get("url", ""))
            if uid:
                cand_url_ids.add(uid)
            cand_websites.add(link.get("website", "").lower())
        
        # Calculate confidence score based on available signals
        confidence = 0.0
        reasons = []
        
        # Signal 1: Exact model number match (highest signal)
        if source_model and cand_model:
            # Normalize both model numbers for comparison
            norm_source = re.sub(r'[\s-]', '', source_model)
            norm_cand = re.sub(r'[\s-]', '', cand_model)
            if norm_source == norm_cand:
                confidence = max(confidence, 0.90)
                reasons.append(f"Exact model number match: {source_model}")
            elif norm_source in norm_cand or norm_cand in norm_source:
                confidence = max(confidence, 0.75)
                reasons.append(f"Partial model number match: {source_model} / {cand_model}")
        
        # Signal 2: URL identifier match (high signal — same product on same store)
        common_url_ids = source_url_ids & cand_url_ids
        if common_url_ids:
            confidence = max(confidence, 0.95)
            reasons.append(f"URL identifier match: {', '.join(common_url_ids)}")
        
        # Signal 3: Brand match + title similarity
        brand_matches = False
        if source_brand and cand_brand:
            if source_brand == cand_brand:
                brand_matches = True
                reasons.append(f"Brand match: {source_brand}")
        
        title_sim = calculate_title_similarity(source_name, cand_name)
        
        if brand_matches and title_sim >= 0.5:
            combined = 0.3 + 0.6 * title_sim  # Brand match boosts base
            confidence = max(confidence, combined)
            reasons.append(f"Title similarity: {title_sim:.0%}")
        elif title_sim >= 0.7:
            confidence = max(confidence, 0.4 + 0.4 * title_sim)
            reasons.append(f"Title similarity: {title_sim:.0%}")
        
        # Filter by minimum confidence
        if confidence >= min_confidence:
            # Get current price from candidate's active links
            cand_prices = [
                link.get("current_price") 
                for link in candidate.get("links", []) 
                if link.get("is_active", True) and link.get("current_price") is not None
            ]
            current_price = min(cand_prices) if cand_prices else None
            
            matches.append({
                "product_id": candidate["id"],
                "product_name": cand_name,
                "confidence": round(confidence, 2),
                "match_reasons": reasons,
                "websites": sorted(list(cand_websites)),
                "current_price": current_price,
            })
    
    # Sort by confidence descending
    matches.sort(key=lambda m: m["confidence"], reverse=True)
    
    return matches
