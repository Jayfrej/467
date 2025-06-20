from flask import Flask, request, jsonify
import logging
from datetime import datetime
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .mt5_handler import MT5Handler
from .config import Config

app = Flask(__name__)
logger = logging.getLogger(__name__)

config = Config()
mt5_handler = None

def send_error_email(app_config, error_details):
    """Sends an email notification when an error occurs."""
    if not all([app_config.SENDER_EMAIL, app_config.SENDER_PASSWORD, app_config.RECEIVER_EMAIL]):
        logger.warning("Email alert configuration is incomplete. Skipping email notification.")
        return
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = "CRITICAL ERROR: Trading Bot Alert"
        message["From"] = app_config.SENDER_EMAIL
        message["To"] = app_config.RECEIVER_EMAIL
        html = f"""
        <html><body>
            <h2>Trading Bot Alert</h2>
            <p>An exception or error occurred while processing a request.</p>
            <p><b>Details:</b></p>
            <pre><code>{error_details}</code></pre>
        </body></html>
        """
        message.attach(MIMEText(html, "html"))
        with smtplib.SMTP(app_config.SMTP_SERVER, app_config.SMTP_PORT) as server:
            server.starttls()
            server.login(app_config.SENDER_EMAIL, app_config.SENDER_PASSWORD)
            server.sendmail(app_config.SENDER_EMAIL, app_config.RECEIVER_EMAIL, message.as_string())
        logger.info("Successfully sent error alert email.")
    except Exception as e:
        logger.error(f"FATAL: Could not send notification email. Reason: {e}")

def initialize_mt5():
    """Initialize MT5 connection using the global config"""
    global mt5_handler
    mt5_handler = MT5Handler(
        account=config.MT5_ACCOUNT,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
        path=config.MT5_PATH,
        symbol_suffix=config.MT5_DEFAULT_SUFFIX
    )
    if not mt5_handler.connect():
        logger.error("Failed to connect to MT5")
        return False
    return True

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle TradingView webhook with centralized error handling and long/short support."""
    global mt5_handler
    
    try:
        data = request.get_json()
        
        if not data:
            raise ValueError("No data received or not in JSON format.")
            
        logger.info(f"Received webhook: {data}")
        
        symbol = data.get('symbol', '')
        action = data.get('action', '')
        volume = data.get('volume', config.DEFAULT_VOLUME)
        
        if not symbol or not action:
            raise ValueError("Missing required fields: 'symbol' or 'action' are required.")
            
        try:
            volume = float(volume)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid volume format: '{volume}'. Must be a number.")
            
        if not mt5_handler or not mt5_handler.connected:
            raise ConnectionError("MT5 is not connected. Please check the connection.")

        action_lower = action.lower()
        if action_lower not in ['buy', 'sell', 'close', 'long', 'short']:
            raise ValueError(f"Unknown or unsupported action: '{action}'.")
        
        # Translate 'long'/'short' to 'buy'/'sell'
        trade_action = action_lower
        if trade_action == 'long':
            trade_action = 'buy'
        elif trade_action == 'short':
            trade_action = 'sell'
            
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')
        
        result = mt5_handler.place_order(
            symbol=symbol,
            action=trade_action,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        if not result:
            raise Exception("Order failed. MT5Handler returned a negative result.")
        
        logger.info(f"Order successfully processed: {result}")
        return jsonify({"status": "success", "message": f"{action.upper()} order processed", "data": result}), 200
            
    except Exception as e:
        error_message = str(e)
        full_traceback = traceback.format_exc()
        logger.error(f"Error processing webhook: {error_message}", exc_info=False)
        send_error_email(config, full_traceback) 
        status_code = 400 if isinstance(e, ValueError) else 500
        if isinstance(e, ConnectionError): status_code = 503
        return jsonify({"error": error_message}), status_code

# Aliases for the webhook endpoint
@app.route('/trade', methods=['POST'])
def trade():
    return webhook()

# Note: You would add other endpoints like /positions, /account etc. here if needed.