import os
import logging
import datetime

logger = logging.getLogger("whatsapp_notifier")

def send_whatsapp_alert(to_phone: str, product_title: str, price: float, url: str) -> bool:
    """
    Sends a WhatsApp message alert when a price drops below the user's target threshold.
    If Twilio credentials are not set in the environment, falls back to logging the alert to logs/whatsapp_alerts.log.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.environ.get("TWILIO_FROM_WHATSAPP", "whatsapp:+14155238886") # Twilio Sandbox Number by default

    message_body = f"🎯 *Price Alert!* The tracked item *{product_title}* has dropped to *INR {price:.2f}*!\nCheck details and buy here: {url}"

    # Verify if Twilio API keys are fully set
    if account_sid and auth_token:
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            
            # Format to-phone standard: ensure whatsapp: prefix
            to_formatted = to_phone
            if not to_formatted.startswith("whatsapp:"):
                to_formatted = f"whatsapp:{to_formatted}"
                
            message = client.messages.create(
                body=message_body,
                from_=from_whatsapp,
                to=to_formatted
            )
            logger.info("WhatsApp notification sent successfully via Twilio SID: %s", message.sid)
            return True
        except Exception as e:
            logger.error("Failed to send WhatsApp message via Twilio: %s. Falling back to log file.", e)
            
    # Fallback to local logs directory file
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    whatsapp_log_file = os.path.join(log_dir, "whatsapp_alerts.log")
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (
            f"[{timestamp}] ALERT DISPATCHED TO {to_phone}\n"
            f"Message: {message_body}\n"
            f"--------------------------------------------------\n"
        )
        
        with open(whatsapp_log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
        logger.info("[Mock Mode] WhatsApp alert written to file: %s", whatsapp_log_file)
        return True
    except Exception as e:
        logger.error("Could not write WhatsApp fallback alert: %s", e)
        return False
