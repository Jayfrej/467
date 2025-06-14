from flask import Flask, request, jsonify
import logging
from datetime import datetime
from .mt5_handler import MT5Handler
from .config import Config

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Initialize MT5 handler
mt5_handler = None

def initialize_mt5():
    """Initialize MT5 connection"""
    global mt5_handler
    config = Config()
    
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
    """Handle TradingView webhook"""
    global mt5_handler
    
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # Extract required fields
        symbol = data.get('symbol', '')
        action = data.get('action', '')
        volume = data.get('volume', Config().DEFAULT_VOLUME)
        
        # Validate required fields
        if not symbol or not action:
            return jsonify({"error": "Missing required fields: symbol, action"}), 400
        
        # Convert volume to float
        try:
            volume = float(volume)
        except (ValueError, TypeError):
            volume = float(Config().DEFAULT_VOLUME)
        
        logger.info(f"Received webhook: {action} {volume} {symbol}")
        
        # Check MT5 connection
        if not mt5_handler or not mt5_handler.connected:
            logger.error("MT5 not connected")
            return jsonify({"error": "MT5 not connected"}), 500
        
        # Process the order
        if action.lower() in ['buy', 'sell', 'close']:
            # Get optional parameters
            stop_loss = data.get('stop_loss')
            take_profit = data.get('take_profit')
            
            # Place order
            result = mt5_handler.place_order(
                symbol=symbol,
                action=action,
                volume=volume,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if result:
                logger.info(f"Order result: {result}")
                return jsonify({
                    "status": "success",
                    "message": f"{action.upper()} order processed",
                    "data": result
                }), 200
            else:
                logger.error("Failed to process order")
                return jsonify({"error": "Failed to process order"}), 500
        else:
            logger.error(f"Unknown action: {action}")
            return jsonify({"error": f"Unknown action: {action}"}), 400
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/trade', methods=['POST'])
def trade():
    """Alternative endpoint for trading (same as webhook)"""
    return webhook()

@app.route('/positions', methods=['GET'])
def get_positions():
    """Get current positions"""
    global mt5_handler
    
    try:
        if not mt5_handler or not mt5_handler.connected:
            return jsonify({"error": "MT5 not connected"}), 500
        
        symbol = request.args.get('symbol')
        positions = mt5_handler.get_positions(symbol)
        
        # Convert positions to JSON serializable format
        positions_data = []
        for pos in positions:
            positions_data.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == 0 else "SELL",
                "volume": pos.volume,
                "price_open": pos.price_open,
                "price_current": pos.price_current,
                "profit": pos.profit,
                "time": str(pos.time)
            })
        
        return jsonify({
            "status": "success",
            "positions": positions_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/close', methods=['POST'])
def close_positions():
    """Close positions by volume"""
    global mt5_handler
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        symbol = data.get('symbol', '')
        volume = data.get('volume', 0)
        
        if not symbol or volume <= 0:
            return jsonify({"error": "Missing required fields: symbol, volume"}), 400
        
        if not mt5_handler or not mt5_handler.connected:
            return jsonify({"error": "MT5 not connected"}), 500
        
        # Close positions
        result = mt5_handler.place_order(
            symbol=symbol,
            action='close',
            volume=float(volume)
        )
        
        if result:
            return jsonify({
                "status": "success",
                "message": f"Closed {volume} lots for {symbol}",
                "data": result
            }), 200
        else:
            return jsonify({"error": "Failed to close positions"}), 500
            
    except Exception as e:
        logger.error(f"Error closing positions: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/account', methods=['GET'])
def get_account():
    """Get account information"""
    global mt5_handler
    
    try:
        if not mt5_handler or not mt5_handler.connected:
            return jsonify({"error": "MT5 not connected"}), 500
        
        account_info = mt5_handler.get_account_info()
        
        if account_info:
            return jsonify({
                "status": "success",
                "account": account_info
            }), 200
        else:
            return jsonify({"error": "Failed to get account info"}), 500
            
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    global mt5_handler
    
    mt5_status = "connected" if mt5_handler and mt5_handler.connected else "disconnected"
    
    return jsonify({
        "status": "healthy",
        "mt5_status": mt5_status,
        "timestamp": str(datetime.now())
    }), 200

if __name__ == '__main__':
    # Initialize MT5 connection
    if initialize_mt5():
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        logger.error("Failed to initialize MT5 connection")