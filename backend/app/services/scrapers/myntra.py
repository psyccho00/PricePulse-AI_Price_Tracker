import json
import re
from bs4 import BeautifulSoup
from typing import Optional, Tuple

def scrape_myntra(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[str], bool, Optional[str]]:
    """
    Parses Myntra HTML structure for title, price, availability, and image URL.
    First attempts JSON extraction of window.__myx script, then falls back to CSS selectors.
    """
    title = None
    price_as_float = None
    in_stock = True
    image_url = None

    # Method 1: Extract from JSON payload (window.__myx)
    try:
        for script in soup.find_all("script"):
            if script.string and "window.__myx" in script.string:
                # Extract JSON using regex
                match = re.search(r"window\.__myx\s*=\s*({.*?});", script.string)
                if not match:
                    match = re.search(r"window\.__myx\s*=\s*({.*})", script.string)
                
                if match:
                    data = json.loads(match.group(1))
                    pdp_data = data.get("pdpData", {})
                    if pdp_data:
                        # Construct title: Brand + Name
                        brand = pdp_data.get("brand")
                        name = pdp_data.get("name")
                        if isinstance(brand, dict):
                            brand = brand.get("name") or brand.get("title") or str(brand)
                        if isinstance(name, dict):
                            name = name.get("name") or name.get("title") or str(name)
                            
                        if brand and name:
                            title = f"{brand} - {name}"
                        else:
                            title = name or brand

                        # Extract price
                        price_info = pdp_data.get("price", {})
                        if price_info:
                            # discounted price is current price, mrp is base
                            price_val = price_info.get("discounted") or price_info.get("mrp")
                            if price_val:
                                price_as_float = float(price_val)

                        # Extract stock availability
                        sizes = pdp_data.get("sizes", [])
                        if sizes:
                            in_stock = any(size.get("available", False) for size in sizes)
                        else:
                            # If no size array, check inventory indicator
                            in_stock = pdp_data.get("inStock", True)

                        # Extract image url
                        media = pdp_data.get("media", {})
                        albums = media.get("albums", [])
                        if albums:
                            for album in albums:
                                images = album.get("images", [])
                                if images:
                                    image_url = images[0].get("src")
                                    break
                        
                        if image_url and "($height)" in image_url:
                            image_url = image_url.replace("($height)", "360").replace("($width)", "270").replace("($qualityPercentage)", "80")

                        return price_as_float, title, in_stock, image_url
    except Exception as e:
        # Fallback if JSON parsing fails
        print(f"Myntra JSON parse exception: {e}")

    # Method 2: Fallback HTML selectors
    # Title
    title_element = soup.select_one("h1.pdp-title")
    name_element = soup.select_one("h1.pdp-name")
    if title_element and name_element:
        title = f"{title_element.get_text().strip()} - {name_element.get_text().strip()}"
    elif name_element:
        title = name_element.get_text().strip()
    elif title_element:
        title = title_element.get_text().strip()

    # Price
    price_element = soup.select_one("span.pdp-price") or soup.select_one(".pdp-discount")
    if price_element:
        try:
            # Myntra prices are in the format "Rs. 1299"
            price_text = price_element.get_text().replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
            price_as_float = float(price_text)
        except ValueError:
            pass

    # Availability
    out_of_stock_element = soup.select_one(".pdp-outOfStock") or soup.select_one(".size-buttons-out-of-stock")
    if out_of_stock_element:
        in_stock = False

    # Image
    img_element = (
        soup.select_one("div.image-grid-container img") or
        soup.select_one("img.image-grid-image") or
        soup.select_one("div.pdp-image-container img")
    )
    if img_element:
        image_url = img_element.get("src")

    # Clean Myntra image template URL parameters
    if image_url and "($height)" in image_url:
        image_url = image_url.replace("($height)", "360").replace("($width)", "270").replace("($qualityPercentage)", "80")

    return price_as_float, title, in_stock, image_url
