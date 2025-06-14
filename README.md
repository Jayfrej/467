# TradingView Alerts to MT5 Integration

This project enables automated trading by connecting TradingView alerts to MetaTrader 5. It creates a local web server that receives webhook notifications from TradingView and executes trades in MT5 based on the parameters provided in the alert.


## Architecture

![Screenshot 2025-06-13 000921](https://github.com/user-attachments/assets/dd4d86f8-e871-4b48-ada2-a4f1c00ef3bf)


## Key Features

- **Webhook Server**: Receives trading signals from TradingView
- **MT5 Integration**: Executes trades directly in your MetaTrader 5 platform
- **Symbol Suffix Support**: Handles broker-specific symbol naming conventions
- **Position Management**: View and close positions through API endpoints
- **Secure Tunneling**: Makes your local server accessible to TradingView using Ngrok

## Requirements

- Python 3.11
- MetaTrader 5 platform installed
- TradingView account (Pro or Premium for webhook alerts)
- Ngrok account (free tier is sufficient) for creating the webhook tunnel https://ngrok.com/
- Postman for troubleshooting and API testing (optional)

## Project Structure

```
tradingview-alerts-to-metatrader5/
│
├── app/                           # Main application package
│   ├── __init__.py                # Package initialization
│   ├── config.py                  # Configuration from .env
│   ├── mt5_handler.py             # MT5 connection and trading logic
│   ├── server.py                  # Flask server for webhooks
│   └── utils.py                   # Utility functions
│
├── docs/                          # Documentation files
│   ├── images/                    # Image assets
│   └── README.md                  # Project documentation
│
├── postman/                       # Postman collection for API testing
│   ├── README.md                  # Postman setup instructions
│   └── postman_collection.json    # Postman collection
│
├── scripts/                       # Helper scripts
│   ├── ngrok_setup.py             # Script to setup and run Ngrok
│   ├── run_server_only.py         # Run Flask server without Ngrok
│   ├── run_ngrok_only.py          # Run Ngrok without Flask server
│   └── test_mt5_connection.py     # Test MT5 connection
│
├── .env.example                   # Example environment variables
├── .gitignore                     # Git ignore file
├── main.py                        # Main entry point
├── README.md                      # This documentation
└── requirements.txt               # Project dependencies
```

## Installation

1. **Clone the repository**: open CMD![Screenshot 2025-06-14 225440](https://github.com/user-attachments/assets/b295a41c-2b12-457d-8b74-7b89b08e3c08)

   ```bash
   cd %HOMEPATH%\Downloads
   git clone https://github.com/Jayfrej/4607.git
   cd 4607
   ```

2. **Create a virtual environment**:if (The system cannot find the path specified) put it again
   ```bash
   python -m venv venv
   ```
2.1. **Create a virtual environment**:
   ```bash
   venv\Scripts\activate.bat
   ```

3. **Install dependencies**:
   ```bash
   cd C:\Users\User\Downloads\4607
   pip install -r requirements.txt
      ```

4. **Configure environment variables**:
   ```bash
   copy .env.example .env
   ```

5. **Edit the `.env` file** with your MT5 account details and broker settings:

   ```
   # MT5 Configuration
   MT5_ACCOUNT=12345678
   MT5_PASSWORD=your-password
   MT5_SERVER=your-broker-server
   MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe


   # MT5 Symbol Settings
   #MT5_DEFAULT_SUFFIX= Not put anything in here / Make it from TradingView alert
   MT5_DEFAULT_SUFFIX=

   # Trading Parameters
   # DEFAULT_VOLUME=0.01
   # DEFAULT_STOP_LOSS=100
   # DEFAULT_TAKE_PROFIT=200
   
   ```

6. **Ngrok**:  Sign up and looking for Your Authtoken and put in .env![Screenshot 2025-06-14 225752](https://github.com/user-attachments/assets/8be791ec-b256-417b-b53d-e7c3d99d6491)


7. **MT5_PATH**:right click on your program and copy (.exe )![Screenshot 2025-06-14 230043](https://github.com/user-attachments/assets/5b21d87c-d40d-40dc-b8b8-935c6d35246f)

   
8. **Go MT5 press F4 put this code/save as EA**![Screenshot 2025-06-14 230259](https://github.com/user-attachments/assets/7d8d1a7f-3359-40be-8e04-dfb2d9912d4a)


```bash
//+------------------------------------------------------------------+
//|                                                  TradingWebhookEA.mq5|
//|                        Fixed MQL5 Version (No Trade.mqh)            |
//+------------------------------------------------------------------+
#property strict

input string WebhookURL = "http://127.0.0.1:5000/webhook"; // Local Flask URL
input int PollingInterval = 5; // วินาที
input double DefaultVolume = 0.01; // Default lot size
input int Slippage = 10; // Slippage in points
input string TradeComment = "WebhookEA"; // Order comment
input int MagicNumber = 12345; // Magic number for orders

datetime last_poll_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("WebhookEA initialized. Polling URL: ", WebhookURL);
   Print("Make sure to add the URL to Tools->Options->Expert Advisors->Allow WebRequest");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if (TimeCurrent() - last_poll_time < PollingInterval)
      return;
   
   string headers = "";
   char data[];
   char result[];
   string result_headers;
   int timeout = 5000;
   
   ResetLastError();
   
   int response = WebRequest(
      "GET",
      WebhookURL,
      headers,
      timeout,
      data,
      result,
      result_headers
   );
   
   if (response == 200 && ArraySize(result) > 0)
   {
      string json_result = CharArrayToString(result);
      Print("Webhook response: ", json_result);
      
      // Parse JSON response
      string action = GetValue(json_result, "action");
      string symbol = GetValue(json_result, "symbol");
      double volume = StringToDouble(GetValue(json_result, "volume"));
      
      // Use default volume if not specified
      if (volume <= 0)
         volume = DefaultVolume;
      
      // Validate symbol and action
      if (symbol == "" || action == "")
      {
         Print("Invalid signal: action=", action, ", symbol=", symbol);
         last_poll_time = TimeCurrent();
         return;
      }
      
      // Use current symbol if different symbol specified
      if (symbol != Symbol())
      {
         Print("Signal for different symbol: ", symbol, " (using current: ", Symbol(), ")");
         symbol = Symbol();
      }
      
      // Execute trades using native MQL5 functions
      if (action == "buy")
      {
         ExecuteBuyOrder(symbol, volume);
      }
      else if (action == "sell")
      {
         ExecuteSellOrder(symbol, volume);
      }
      else
      {
         Print("Unknown action: ", action);
      }
   }
   else
   {
      if (response != 200 && response != -1)
         Print("WebRequest failed with response code: ", response);
      
      int error = GetLastError();
      if (error != 0)
         Print("WebRequest error: ", error, " - ", GetErrorDescription(error));
   }
   
   last_poll_time = TimeCurrent();
}

//+------------------------------------------------------------------+
//| Execute Buy Order using MqlTradeRequest                         |
//+------------------------------------------------------------------+
void ExecuteBuyOrder(string symbol, double volume)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = symbol;
   request.volume = volume;
   request.type = ORDER_TYPE_BUY;
   request.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   request.deviation = Slippage;
   request.magic = MagicNumber;
   request.comment = TradeComment;
   request.type_filling = ORDER_FILLING_FOK;
   
   if (OrderSend(request, result))
   {
      Print("Buy order sent successfully for ", symbol, 
            " Volume: ", volume, 
            " Price: ", request.price,
            " Ticket: ", result.order);
   }
   else
   {
      Print("Failed to send buy order. Error: ", GetLastError(), 
            " Result: ", result.retcode, 
            " Comment: ", result.comment);
   }
}

//+------------------------------------------------------------------+
//| Execute Sell Order using MqlTradeRequest                        |
//+------------------------------------------------------------------+
void ExecuteSellOrder(string symbol, double volume)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = symbol;
   request.volume = volume;
   request.type = ORDER_TYPE_SELL;
   request.price = SymbolInfoDouble(symbol, SYMBOL_BID);
   request.deviation = Slippage;
   request.magic = MagicNumber;
   request.comment = TradeComment;
   request.type_filling = ORDER_FILLING_FOK;
   
   if (OrderSend(request, result))
   {
      Print("Sell order sent successfully for ", symbol, 
            " Volume: ", volume, 
            " Price: ", request.price,
            " Ticket: ", result.order);
   }
   else
   {
      Print("Failed to send sell order. Error: ", GetLastError(), 
            " Result: ", result.retcode, 
            " Comment: ", result.comment);
   }
}

//+------------------------------------------------------------------+
//| Simple JSON parser function                                      |
//+------------------------------------------------------------------+
string GetValue(string json, string key)
{
   string pattern = "\"" + key + "\":\"";
   int start = StringFind(json, pattern);
   
   if (start == -1) 
   {
      // Try without quotes (for numeric values)
      pattern = "\"" + key + "\":";
      start = StringFind(json, pattern);
      if (start == -1) return "";
      start += StringLen(pattern);
      
      // Skip whitespace
      while (start < StringLen(json) && StringGetCharacter(json, start) == 32)
         start++;
      
      // Find the end (comma, closing brace, or end of string)
      int end = start;
      while (end < StringLen(json))
      {
         int ch = StringGetCharacter(json, end);
         if (ch == 44 || ch == 125 || ch == 93) // comma, }, ]
            break;
         end++;
      }
      
      if (end <= start) return "";
      string value = StringSubstr(json, start, end - start);
      StringTrimLeft(value);
      StringTrimRight(value);
      return value;
   }
   
   start += StringLen(pattern);
   int end = StringFind(json, "\"", start);
   if (end == -1) return "";
   
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Get error description                                            |
//+------------------------------------------------------------------+
string GetErrorDescription(int error_code)
{
   switch(error_code)
   {
      case 4060: return "No internet connection";
      case 4014: return "Unknown symbol";
      case 4751: return "Invalid URL";
      case 4752: return "Failed to connect to specified URL";
      case 4753: return "Timeout exceeded";
      case 4754: return "HTTP error";
      case 5203: return "URL not allowed for WebRequest";
      case 4809: return "Resource not found";
      default: return "Error code: " + IntegerToString(error_code);
   }
}
```

9. **run**: copy webhook to TV and MT5
 ![image](https://github.com/user-attachments/assets/e48bd5fc-08f9-4bfb-8556-095d4df9c84c)
![image](https://github.com/user-attachments/assets/fba7f04a-11c2-4a70-a856-353998849324)
![Screenshot 2025-06-14 230457](https://github.com/user-attachments/assets/7eed188a-7cd3-4b8b-88b0-960be4948200)



   ```bash
   python main.py
      ```


## Setting Up TradingView Alerts

1. **Create an alert in TradingView**:

   - Set up your indicator or strategy
   - Click "Create Alert"
   - Configure your alert conditions

2. **Configure the webhook**:

   - In the "Webhook URL" field, paste the Ngrok URL from `webhook_url.txt` (it will look like `https://xxxx.ngrok-free.app/trade`)

3. **Format your alert message as JSON**:

   ```json
   {
   "symbol": "{{ticker}}",
   "action": "{{strategy.order.action}}",
   "volume": "{{strategy.order.contracts}}"
   }
   ```
    Buy 0.1 lot
   
   ```json
   {
   "symbol": "{{ticker}}",
   "action": "buy",
   "volume": "0.1"
   }
   ```
    Sell 0.2 lot
   
    ```json
    {
      "symbol": "{{ticker}}",
      "action": "sell",
      "volume": "0.2"
    }
    ```
      Close 0.05 lot
    ```json
    {
      "symbol": "{{ticker}}",
      "action": "close",
      "volume": "0.05"
    }
    ```

   1. **Use a VPS**:

   - Run the application on a Virtual Private Server for 24/7 operation
   - This ensures your application keeps running even when your computer is off

2. **Replace Ngrok with a proper server**:

   - Register a domain name
   - Use a reverse proxy (Nginx, Apache) with SSL certificates
   - Configure proper port forwarding

3. **Add authentication**:
   - Implement API key authentication for your webhook
   - This prevents unauthorized access to your trading system

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [MetaTrader5 Python Library](https://pypi.org/project/MetaTrader5/)
- [Flask](https://flask.palletsprojects.com/)
- [Ngrok](https://ngrok.com/)
