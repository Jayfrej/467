import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the application"""
    
    def __init__(self):
        # MT5 Configuration
        self.MT5_ACCOUNT = int(os.getenv('MT5_ACCOUNT', 0))
        self.MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
        self.MT5_SERVER = os.getenv('MT5_SERVER', '')
        self.MT5_PATH = os.getenv('MT5_PATH', 'C:\\Program Files\\MetaTrader 5\\terminal64.exe')
        
        # MT5 Symbol Settings
        self.MT5_DEFAULT_SUFFIX = os.getenv('MT5_DEFAULT_SUFFIX', '')
        
        # Trading Parameters
        self.DEFAULT_VOLUME = float(os.getenv('DEFAULT_VOLUME', 0.01))
        self.DEFAULT_STOP_LOSS = int(os.getenv('DEFAULT_STOP_LOSS', 100))
        self.DEFAULT_TAKE_PROFIT = int(os.getenv('DEFAULT_TAKE_PROFIT', 200))
        
        # Ngrok Configuration
        self.NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN', '')
        
        # Server Configuration
        self.SERVER_HOST = os.getenv('FLASK_HOST', os.getenv('SERVER_HOST', '0.0.0.0'))
        self.SERVER_PORT = int(os.getenv('FLASK_PORT', os.getenv('SERVER_PORT', 5000)))
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

        # --- SECTION ADDED FOR EMAIL ALERTS ---
        # Email Alert Configuration
        self.SENDER_EMAIL = os.getenv('SENDER_EMAIL', '')
        self.SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', '')
        self.RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL', '')
        self.SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
        # --- END OF ADDED SECTION ---
        
    def validate(self):
        """Validate configuration"""
        errors = []
        
        if not self.MT5_ACCOUNT:
            errors.append("MT5_ACCOUNT is required in .env file")
            
        if not self.MT5_PASSWORD:
            errors.append("MT5_PASSWORD is required in .env file")
            
        if not self.MT5_SERVER:
            errors.append("MT5_SERVER is required in .env file")
            
        if not os.path.exists(self.MT5_PATH):
            errors.append(f"MT5_PATH does not exist: {self.MT5_PATH}")
            
        if not self.NGROK_AUTH_TOKEN:
            errors.append("NGROK_AUTH_TOKEN is required in .env file")

        # --- SECTION ADDED FOR EMAIL VALIDATION ---
        if not self.SENDER_EMAIL:
            errors.append("SENDER_EMAIL is required in .env file for alerts")
        
        if not self.SENDER_PASSWORD:
            errors.append("SENDER_PASSWORD is required in .env file for alerts")

        if not self.RECEIVER_EMAIL:
            errors.append("RECEIVER_EMAIL is required in .env file for alerts")
        # --- END OF ADDED SECTION ---
            
        return errors
    
    def __str__(self):
        """String representation of config (without sensitive data)"""
        return f"""
MT5 Configuration:
- Account: {self.MT5_ACCOUNT}
- Server: {self.MT5_SERVER}
- Path: {self.MT5_PATH}
- Symbol Suffix: {self.MT5_DEFAULT_SUFFIX}

Trading Parameters:
- Default Volume: {self.DEFAULT_VOLUME}
- Default Stop Loss: {self.DEFAULT_STOP_LOSS}
- Default Take Profit: {self.DEFAULT_TAKE_PROFIT}

Server Configuration:
- Host: {self.SERVER_HOST}
- Port: {self.SERVER_PORT}
- Debug: {self.DEBUG}

{self.get_email_config_str()}
"""

    # --- METHOD ADDED FOR EMAIL CONFIG STRING ---
    def get_email_config_str(self):
        """Returns string representation of email config"""
        if self.SENDER_EMAIL:
            return f"""Email Alert Configuration:
- Sender: {self.SENDER_EMAIL}
- Receiver: {self.RECEIVER_EMAIL}
- SMTP Server: {self.SMTP_SERVER}:{self.SMTP_PORT}"""
        return "Email Alert Configuration: Not Configured"
    # --- END OF ADDED METHOD ---