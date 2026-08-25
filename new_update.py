import smtplib
from bs4 import BeautifulSoup
import requests
import os
import schedule
import time
from dotenv import load_dotenv

# Load .env
load_dotenv()

def check_price():
    print("Checking price...")

    live_url = "https://www.amazon.com/dp/B075CYMYK6?psc=1&ref_=cm_sw_r_cp_ud_ct_FM9M699VKHTT47YD50Q6"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    }

    try:
        response = requests.get(live_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        price_element = soup.select_one("span.a-price span.a-offscreen")
        if not price_element:
            print("Price not found!")
            return

        price = price_element.get_text().replace("$", "").strip()
        price_as_float = float(price)

        title = soup.find(id="productTitle").get_text().strip()


        # Target price at which we want to buy
        buy_price = 100

        if price_as_float < buy_price:
            message = f"{title} is on sale for ${price}!"


# ======================  SENDS EMAIL  ===========================

            with smtplib.SMTP(os.environ["SMTP_ADDRESS"], port=587) as connection:
                connection.starttls()
                connection.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_PASSWORD"])
                connection.sendmail(
                    from_addr=os.environ["EMAIL_ADDRESS"],
                    to_addrs=os.environ["EMAIL_ADDRESS"],
                    msg=f"Subject:Amazon Price Alert!\n\n{message}\n{live_url}".encode("utf-8")
                )
            print("Email sent!")
        else:
            print("No price drop. Current price:", price_as_float)

    except Exception as e:
        print("Error occurred:", e)


# ======================  SCHEDULING THE TASK  ===========================

# Run daily at 10:00 AM
schedule.every().day.at("10:00").do(check_price)

print("Scheduler started. Waiting for the scheduled time...")

while True:
    schedule.run_pending()
    time.sleep(60)
