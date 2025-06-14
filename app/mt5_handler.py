import logging
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from .config import (
    MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER, MT5_PATH,
    DEFAULT_VOLUME,
    MT5_DEFAULT_SUFFIX
)

logger = logging.getLogger(__name__)

class MT5Handler:
    """
    Handles all MetaTrader 5 operations including connection and trading
    """
    def __init__(self):
        self.connected = False
        self.volume_column = None
        self.symbol_map = {}  # Cache for symbol mappings
        self.initialize_mt5()
    
    def initialize_mt5(self):
        """Initialize connection to MetaTrader 5"""
        if not mt5.initialize(path=MT5_PATH):
            logger.error(f"MT5 initialize() failed. Error code: {mt5.last_error()}")
            return False
        
        # Connect to the MT5 account
        authorized = mt5.login(MT5_ACCOUNT, password=MT5_PASSWORD, server=MT5_SERVER)
        if not authorized:
            logger.error(f"MT5 login failed. Error code: {mt5.last_error()}")
            mt5.shutdown()
            return False
        
        # Log account information
        account_info = mt5.account_info()
        if account_info:
            account_dict = account_info._asdict()
            logger.info(f"Connected to MT5 - Account: {account_dict['login']}, "
                      f"Server: {account_dict['server']}, "
                      f"Balance: {account_dict['balance']}, "
                      f"Leverage: 1:{account_dict['leverage']}")
        else:
            logger.info("Connected to MT5 but couldn't retrieve account info")
        
        # Test a common symbol to verify data access
        self._check_data_columns()
        
        # Log available symbols for debugging
        common_pairs = ["EURUSD", "GBPUSD", "USDJPY"]
        all_symbols = mt5.symbols_get()
        if all_symbols:
            symbol_names = [s.name for s in all_symbols]
            logger.info(f"Total symbols available: {len(symbol_names)}")
            
            # Find symbols matching common pairs
            for pair in common_pairs:
                matches = [s for s in symbol_names if pair in s]
                if matches:
                    logger.info(f"Found {pair} variations: {matches}")
        
        self.connected = True
        return True
        
    def _check_data_columns(self):
        """Check data column names to handle broker-specific variations"""
        try:
            # Get all symbols to find a valid one to test
            all_symbols = mt5.symbols_get()
            if not all_symbols or len(all_symbols) == 0:
                logger.warning("No symbols found in MT5")
                self.volume_column = None
                return
                
            # Try to find EURUSD or EURUSD.r
            test_symbols = ["EURUSD.r", "EURUSD"]
            test_symbol = None
            
            for symbol in test_symbols:
                if mt5.symbol_select(symbol, True):
                    test_symbol = symbol
                    break
            
            if test_symbol is None:
                # Use the first available symbol
                test_symbol = all_symbols[0].name
                mt5.symbol_select(test_symbol, True)
            
            # Get sample data
            rates = mt5.copy_rates_from_pos(test_symbol, mt5.TIMEFRAME_M1, 0, 1)
            
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                logger.info(f"MT5 data columns for {test_symbol}: {list(df.columns)}")
                # Check if 'volume' exists or if 'tick_volume' is used instead
                if 'volume' in df.columns:
                    self.volume_column = 'volume'
                elif 'tick_volume' in df.columns:
                    self.volume_column = 'tick_volume'
                else:
                    self.volume_column = None
                    logger.warning("Neither 'volume' nor 'tick_volume' column found in MT5 data")
            else:
                logger.warning(f"Couldn't retrieve sample data for {test_symbol}")
                self.volume_column = None
        except Exception as e:
            logger.error(f"Error checking data columns: {str(e)}")
            self.volume_column = None
    
    def check_connection(self):
        """Check if MT5 is still connected, reconnect if needed"""
        if not self.connected or not mt5.terminal_info():
            logger.warning("MT5 connection lost, attempting to reconnect...")
            self.connected = False
            return self.initialize_mt5()
        return True
    
    def list_available_symbols(self):
        """
        Get a list of all available symbols in MT5
        
        Returns:
            list: List of symbol names
        """
        if not self.check_connection():
            return []
            
        # Get all symbols from MT5
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            return []
            
        # Extract symbol names
        symbol_names = [s.name for s in all_symbols]
        return symbol_names
    
    def close_all_positions(self, symbol=None, close_volume=None):
        """
        Close all open positions for a specific symbol or all symbols
        
        Args:
            symbol (str, optional): Symbol to close positions for. If None, closes all positions.
            close_volume (float, optional): Volume to close per position. If None, closes full positions.
            
        Returns:
            dict: Result summary of close operations
        """
        if not self.check_connection():
            return {"success": False, "message": "MT5 connection failed"}
        
        positions = self.get_positions(symbol)
        if not positions:
            return {"success": True, "message": "No positions to close", "closed_count": 0}
        
        closed_count = 0
        failed_count = 0
        results = []
        total_volume_closed = 0.0
        
        # หาก close_volume ระบุมา และมี position หลายตัว ให้แบ่ง volume
        if close_volume is not None and len(positions) > 1:
            # แบ่ง volume ให้แต่ละ position เท่าๆ กัน
            volume_per_position = close_volume / len(positions)
            logger.info(f"Closing {close_volume} total volume across {len(positions)} positions ({volume_per_position} each)")
        else:
            volume_per_position = close_volume
        
        for position in positions:
            result = self.close_position(position['ticket'], volume_per_position)
            results.append(result)
            
            if result['success']:
                closed_count += 1
                total_volume_closed += result.get('volume_closed', 0)
            else:
                failed_count += 1
        
        logger.info(f"Closed {closed_count} positions, {failed_count} failed for symbol: {symbol}, Total volume closed: {total_volume_closed}")
        
        return {
            "success": failed_count == 0,
            "message": f"Closed {closed_count} positions, {failed_count} failed",
            "closed_count": closed_count,
            "failed_count": failed_count,
            "total_volume_closed": total_volume_closed,
            "details": results
        }

    def place_trade(self, symbol, order_type, volume=DEFAULT_VOLUME, 
                   price=0.0, stop_loss=None, take_profit=None, comment="TV Signal", 
                   close_existing=True):
        """
        Place a trade in MT5
        
        Args:
            symbol (str): Trading instrument symbol (e.g., 'EURUSD')
            order_type (str): Order type ('BUY', 'SELL', 'LONG', 'SHORT')
            volume (float): Trade volume in lots
            price (float): Order price (0 for market order)
            stop_loss (float, optional): Ignored - kept for backward compatibility
            take_profit (float, optional): Ignored - kept for backward compatibility
            comment (str): Order comment
            close_existing (bool): Whether to close existing positions before opening new one
            
        Returns:
            dict: Result of the order operation
        """
        if not self.check_connection():
            return {"success": False, "message": "MT5 connection failed"}
        
        # Close existing positions for this symbol if requested
        if close_existing:
            logger.info(f"Closing existing positions for {symbol} before placing new order")
            close_result = self.close_all_positions(symbol)
            logger.info(f"Close result: {close_result['message']}")
        
        # Add a small delay after closing positions to ensure they're processed
        import time
        if close_existing:
            time.sleep(0.5)  # 500ms delay
        
        # Check if the symbol already has the suffix
        if MT5_DEFAULT_SUFFIX and not symbol.endswith(MT5_DEFAULT_SUFFIX):
            mt5_symbol = symbol + MT5_DEFAULT_SUFFIX
            logger.info(f"Adding suffix: {symbol} -> {mt5_symbol}")
        else:
            mt5_symbol = symbol
            
        logger.info(f"Trading symbol: {mt5_symbol}")
        
        # Get symbol info
        symbol_info = mt5.symbol_info(mt5_symbol)
        if symbol_info is None:
            # Try to find similar symbols for debugging
            similar_symbols = []
            all_symbols = mt5.symbols_get()
            if all_symbols:
                base_name = symbol.split('.')[0]
                similar_symbols = [s.name for s in all_symbols if base_name in s.name]
            
            logger.error(f"Symbol {mt5_symbol} not found. Similar symbols: {similar_symbols}")
            return {"success": False, "message": f"Symbol {mt5_symbol} not found"}
        
        if not symbol_info.visible:
            logger.info(f"Symbol {mt5_symbol} is not visible, trying to add it")
            if not mt5.symbol_select(mt5_symbol, True):
                return {"success": False, "message": f"Failed to select symbol {mt5_symbol}"}
        
        # Get current tick data
        tick = mt5.symbol_info_tick(mt5_symbol)
        if tick is None:
            return {"success": False, "message": f"Failed to get market data for {mt5_symbol}"}
        
        # Log tick information for debugging
        logger.info(f"Current {mt5_symbol} prices - Bid: {tick.bid}, Ask: {tick.ask}")
        
        # Set order type and price
        if order_type.upper() in ["BUY", "LONG"]:
            mt5_order_type = mt5.ORDER_TYPE_BUY
            current_price = tick.ask
        elif order_type.upper() in ["SELL", "SHORT"]:
            mt5_order_type = mt5.ORDER_TYPE_SELL
            current_price = tick.bid
        else:
            return {"success": False, "message": f"Invalid order type: {order_type}"}
        
        # Create request structure for market order (without TP/SL)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": float(volume),
            "type": mt5_order_type,
            "price": current_price,
            "deviation": 30,
            "magic": 234000,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the order
        logger.info(f"Sending order: {request}")
        result = mt5.order_send(request)
        
        # Process the result
        if result is None:
            error_code = mt5.last_error()
            logger.error(f"Order failed with error code: {error_code}")
            return {
                "success": False,
                "message": f"Order failed. Error: {error_code}"
            }
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            # Log detailed result for debugging
            result_dict = result._asdict()
            logger.error(f"Order failed. Details: {result_dict}")
            return {
                "success": False,
                "message": f"Order failed. Error code: {result.retcode}",
                "details": result_dict
            }
        
        # Success! Log and return the result
        result_dict = result._asdict()
        logger.info(f"Order executed successfully. Details: {result_dict}")
        return {
            "success": True,
            "message": f"Order executed: {order_type} {symbol}",
            "details": result_dict
        }
    
    def get_positions(self, symbol=None):
        """
        Get open positions
        
        Args:
            symbol (str, optional): Symbol to filter positions. Defaults to None (all positions).
            
        Returns:
            list: List of open positions
        """
        if not self.check_connection():
            return []
        
        # Add suffix if needed
        if symbol is not None and MT5_DEFAULT_SUFFIX and not symbol.endswith(MT5_DEFAULT_SUFFIX):
            mt5_symbol = symbol + MT5_DEFAULT_SUFFIX
            positions = mt5.positions_get(symbol=mt5_symbol)
        else:
            # Use as-is or get all positions
            positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            
        if positions is None or len(positions) == 0:
            return []
            
        # Convert tuples to dictionaries
        result = []
        for position in positions:
            position_dict = position._asdict()
            
            # Remove suffix from the returned symbol for consistency with TradingView
            if MT5_DEFAULT_SUFFIX and position_dict['symbol'].endswith(MT5_DEFAULT_SUFFIX):
                # Store both the broker symbol and the standard symbol
                position_dict['broker_symbol'] = position_dict['symbol']
                position_dict['symbol'] = position_dict['symbol'][:-len(MT5_DEFAULT_SUFFIX)]
                
            result.append(position_dict)
            
        return result
    
    def close_position(self, position_id, close_volume=None):
        """
        Close a specific position by its ticket (full or partial close)
        
        Args:
            position_id (int): Position ticket
            close_volume (float, optional): Volume to close. If None, closes full position
            
        Returns:
            dict: Result of the close operation
        """
        if not self.check_connection():
            return {"success": False, "message": "MT5 connection failed"}
        
        # Get position details
        positions = mt5.positions_get(ticket=position_id)
        if positions is None or len(positions) == 0:
            return {"success": False, "message": f"Position {position_id} not found"}
        
        position = positions[0]
        position_symbol = position.symbol
        
        # Determine volume to close
        if close_volume is None:
            # Close full position
            volume_to_close = position.volume
        else:
            # Close partial - ensure we don't close more than available
            volume_to_close = min(float(close_volume), position.volume)
            
        logger.info(f"Position {position_id} - Total volume: {position.volume}, Closing volume: {volume_to_close}")
        
        # Determine order type for closing
        close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(position_symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position_symbol).ask
        
        # Create request structure
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": position_id,
            "symbol": position_symbol,
            "volume": volume_to_close,  # ใช้ volume ที่คำนวณแล้ว
            "type": close_type,
            "price": price,
            "deviation": 30,
            "magic": 234000,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send the order
        logger.info(f"Closing position {position_id}: {request}")
        result = mt5.order_send(request)
        
        # Process the result
        if result is None:
            error_code = mt5.last_error()
            logger.error(f"Close position failed with error code: {error_code}")
            return {
                "success": False,
                "message": f"Close position failed. Error: {error_code}"
            }
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            result_dict = result._asdict()
            logger.error(f"Close position failed. Details: {result_dict}")
            return {
                "success": False,
                "message": f"Close position failed. Error code: {result.retcode}",
                "details": result_dict
            }
        
        result_dict = result._asdict()
        logger.info(f"Position {position_id} closed successfully. Volume closed: {volume_to_close}, Details: {result_dict}")
        return {
            "success": True,
            "message": f"Position {position_id} closed (Volume: {volume_to_close})",
            "details": result_dict,
            "volume_closed": volume_to_close
        }
    
    def close_session(self):
        """Properly close MT5 connection"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 connection closed")
