import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def send_email_alert(to_email: str, product_title: str, price: float, url: str) -> bool:
    """
    Preserved email notification logic from the user's files.
    Connects to SMTP server, logs in, and dispatches the alert email.
    """
    smtp_address = os.environ.get("SMTP_ADDRESS")
    email_address = os.environ.get("EMAIL_ADDRESS")
    email_password = os.environ.get("EMAIL_PASSWORD")

    if not all([smtp_address, email_address, email_password]):
        print("Notification Error: SMTP environment variables are not fully set in .env")
        return False

    message_body = f"{product_title} is on sale for {price}!\n\nCheck the link: {url}"
    subject = "Amazon Price Alert!"
    
    # Use MIMEText to handle encoding correctly
    msg = MIMEText(message_body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = email_address
    msg["To"] = to_email

    try:
        # SMTP connection setup
        with smtplib.SMTP(smtp_address, port=587) as connection:
            connection.starttls()
            connection.login(email_address, email_password)
            connection.sendmail(
                from_addr=email_address,
                to_addrs=[to_email],
                msg=msg.as_string()
            )
        print(f"Email alert successfully sent to {to_email}!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
