import os
import sys

# Ensure backend package is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.services.scraper import scrape_product, detect_website

def run_tests():
    print("=========================================================")
    # 1. Test URL detection
    print("Testing Website URL Auto-Detection:")
    test_urls = {
        "https://www.amazon.in/Hero-Xpulse-Booking-Ex-Showroom-Polestar/dp/B0D9DLZ2DJ/": "amazon",
        "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm2d83cbb662481": "flipkart",
        "https://www.myntra.com/shoes/nike/nike-men-black-air-max-alpha-trainer-5-training-shoes/21175658/buy": "myntra",
        "https://www.google.com": "unknown"
    }

    for url, expected in test_urls.items():
        detected = detect_website(url)
        print(f"URL: {url[:60]}... \n -> Detected: {detected} (Expected: {expected})")
        assert detected == expected
    print("[OK] URL detection verified successfully.\n")

    # 2. Test Real Scraping (Try to scrape standard active items)
    # Amazon test URL
    amazon_url = "https://www.amazon.in/Hero-Xpulse-Booking-Ex-Showroom-Polestar/dp/B0D9DLZ2DJ/"
    # Flipkart test URL
    flipkart_url = "https://www.flipkart.com/realme-p1-5g-peacock-green-128-gb/p/itm7e679b360b3de"
    # Myntra test URL
    myntra_url = "https://www.myntra.com/tshirts/roadster/roadster-men-black-cotton-pure-cotton-t-shirt/19914486/buy"

    print("=========================================================")
    print("Testing Amazon Scraper on Hero Xpulse:")
    res_amz = scrape_product(amazon_url)
    print_result(res_amz)

    print("=========================================================")
    print("Testing Flipkart Scraper on Realme Phone:")
    res_fk = scrape_product(flipkart_url)
    print_result(res_fk)

    print("=========================================================")
    print("Testing Myntra Scraper on Roadster T-Shirt:")
    res_my = scrape_product(myntra_url)
    print_result(res_my)
    print("=========================================================")

def print_result(res):
    print(f"Website:    {res['website']}")
    print(f"Title:      {res['title']}")
    print(f"Price:      {res['price']}")
    print(f"In Stock:   {res['in_stock']}")
    print(f"Image URL:  {res.get('image_url')}")
    if res.get('error'):
        print(f"Error:      {res['error']}")
    else:
        print("Scrape Status: Success")

if __name__ == "__main__":
    run_tests()
