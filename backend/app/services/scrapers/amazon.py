from bs4 import BeautifulSoup
from typing import Optional, Tuple
import json

def scrape_amazon(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[str], bool, Optional[str]]:
    """
    Parses Amazon HTML structure for title, price, availability, and image URL.
    Preserves selectors from original files.
    """
    # 1. Parse Title
    title = None
    title_element = soup.find(id="productTitle")
    if title_element:
        title = title_element.get_text().strip()

    # 2. Parse Price
    price_as_float = None

    # Try 1: class="a-price-whole" (amazon.in, etc.)
    price_element = soup.find(class_="a-price-whole")
    if price_element:
        try:
            price_clean = price_element.get_text().replace(',', '').strip()
            price_as_float = float(price_clean)
        except ValueError:
            pass

    # Try 2: span.a-price span.a-offscreen (amazon.com, etc.)
    if price_as_float is None:
        price_element = soup.select_one("span.a-price span.a-offscreen") or soup.find(class_="a-offscreen")
        if price_element:
            try:
                price_clean = price_element.get_text().replace('$', '').replace(',', '').strip()
                price_as_float = float(price_clean)
            except ValueError:
                pass

    # 3. Parse Availability
    in_stock = True
    avail_element = soup.find(id="availability")
    if avail_element:
        avail_text = avail_element.get_text().lower()
        if "currently unavailable" in avail_text or "out of stock" in avail_text or "currently out of stock" in avail_text:
            in_stock = False
    else:
        # Fallback keyword checking on the body text
        body_text = soup.get_text().lower()
        if "currently unavailable" in body_text and "amazon" in body_text:
            # Check if it is really unavailable
            in_stock = False

    # 4. Parse Image URL
    image_url = None
    landing_img = soup.find(id="landingImage") or soup.find(id="imgBlkFront") or soup.select_one("#main-image-container img")
    if landing_img:
        dynamic_img = landing_img.get("data-a-dynamic-image")
        if dynamic_img:
            try:
                urls = json.loads(dynamic_img)
                if urls:
                    image_url = list(urls.keys())[0]
            except Exception:
                pass
        if not image_url:
            image_url = landing_img.get("src") or landing_img.get("data-old-hires")

    return price_as_float, title, in_stock, image_url
