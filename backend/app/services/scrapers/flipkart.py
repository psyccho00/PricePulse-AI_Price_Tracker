from bs4 import BeautifulSoup
from typing import Optional, Tuple

def scrape_flipkart(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[str], bool, Optional[str]]:
    """
    Parses Flipkart HTML structure for title, price, availability, and image URL.
    """
    # 1. Parse Title
    title = None
    # Class styles: VU-ZEz (new), B_NuCI (old)
    title_element = soup.select_one("h1.VU-ZEz") or soup.select_one("span.B_NuCI") or soup.find("h1")
    if title_element:
        title = title_element.get_text().strip()

    # 2. Parse Price
    price_as_float = None
    # Class styles: Nx9ZHg (new), _30jeq3 (old), _16Jk6d (mobile/alternative)
    price_element = (
        soup.select_one("div.Nx9ZHg") or 
        soup.select_one("div._30jeq3") or 
        soup.select_one("div._16Jk6d") or
        soup.select_one("div.Ufi86t")
    )
    if price_element:
        try:
            price_text = price_element.get_text()
            # Remove currency symbol (₹) and commas
            price_clean = price_text.replace('₹', '').replace(',', '').strip()
            price_as_float = float(price_clean)
        except ValueError:
            pass

    # 3. Parse Availability
    in_stock = True
    # Flipkart shows "Sold Out" or "This item is currently out of stock" in stock alerts
    body_text = soup.get_text().lower()
    if "sold out" in body_text or "out of stock" in body_text:
        # Verify if it's the product availability message
        stock_alerts = soup.select("div._1921qB") or soup.select("div._1O9Y6q") or soup.select(".W894nn")
        if stock_alerts:
            in_stock = False
        else:
            # Let's double check if there are no Add to Cart or Buy Now buttons
            buy_buttons = soup.select("button._2KpZ6l") or soup.select("button.QqFHMw") or soup.select(".N9bx7u")
            if buy_buttons and any("out of stock" in b.get_text().lower() or "sold out" in b.get_text().lower() for b in buy_buttons):
                in_stock = False
            elif not buy_buttons and ("sold out" in body_text or "out of stock" in body_text):
                in_stock = False

    # 4. Parse Image URL
    image_url = None
    img_element = (
        soup.select_one("img.DByoEF") or
        soup.select_one("div.CXW8mj img") or
        soup.select_one("img._396cs4") or
        soup.select_one("img._2r_l1q") or
        soup.select_one("div._3dAdhm img") or
        soup.select_one("img[src*='/image/']")
    )
    if img_element:
        image_url = img_element.get("src")

    return price_as_float, title, in_stock, image_url
