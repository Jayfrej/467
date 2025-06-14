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
        
    def validate(self):
        """Validate configuration"""
        errors = []
        
        if not self.MT5_ACCOUNT:
            errors.append("MT5_ACCOUNT is required")
            
        if not self.MT5_PASSWORD:
            errors.append("MT5_PASSWORD is required")
            
        if not self.MT5_SERVER:
            errors.append("MT5_SERVER is required")
            
        if not os.path.exists(self.MT5_PATH):
            errors.append(f"MT5_PATH does not exist: {self.MT5_PATH}")
            
        if not self.NGROK_AUTH_TOKEN:
            errors.append("NGROK_AUTH_TOKEN is required")
            
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
"""