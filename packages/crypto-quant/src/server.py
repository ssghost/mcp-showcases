from mcp.server.fastmcp import FastMCP
import requests
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import traceback

mcp = FastMCP("Crypto Quant")

def get_data(symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
    symbol = symbol.upper().replace("-", "").replace("_", "")
    if not symbol.endswith("USDT") and not symbol.endswith("USD"):
        symbol = f"{symbol}USDT"
    if symbol.endswith("USD") and not symbol.endswith("USDT"):
        symbol = symbol.replace("USD", "USDT")

    print(f"Fetching Binance data for {symbol}...")    
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Binance API Error: {response.text}.")
            return pd.DataFrame()   
        data = response.json()
        if not isinstance(data, list):
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=[
            "Open Time", "Open", "High", "Low", "Close", "Volume",
            "Close Time", "Quote Asset Volume", "Number of Trades",
            "Taker Buy Base Asset Volume", "Taker Buy Quote Asset Volume", "Ignore"
        ])
        numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, axis=1)
        df["Date"] = pd.to_datetime(df["Open Time"], unit="ms")
        df.set_index("Date", inplace=True)
        return df

    except Exception as e:
        print(f"Network Error: {str(e)}.")
        print(traceback.format_exc())
        return pd.DataFrame()

@mcp.tool()
def calculate_indicators(ticker: str) -> str:
    try:
        df = get_data(ticker)
        
        if df.empty:
            return f"Error: No data found for ticker {ticker}. Please check your internet connection or ticker name."

        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.bbands(length=20, std=2, append=True)

        cols_to_show = ['Close', 'RSI_14', 'MACD_12_26_9', 'MACDs_12_26_9', 'BBU_20_2.0', 'BBL_20_2.0']
        existing_cols = [c for c in cols_to_show if c in df.columns]
        recent_data = df[existing_cols].tail(5)
        return f"Technical Analysis for {ticker}:\n" + recent_data.to_string()
    
    except Exception as e:
        return f"Error calculating indicators: {str(e)}"

@mcp.tool()
def backtest(ticker: str, strategy: str = "rsi", **kwargs) -> str:
    try:
        df = get_data(ticker) 
        if df.empty:
            return f"Error: No data found for {ticker}."

        STRATEGY_MAP = {
            "rsi": rsi_strategy
        }
        
        selected_strategy_fn = STRATEGY_MAP.get(strategy.lower())
        if not selected_strategy_fn:
            return f"Error: Strategy '{strategy}' not found."

        df = selected_strategy_fn(df, **kwargs)

        df['Market_Return'] = df['Close'].pct_change()
        df['Strategy_Return'] = df['Position'].shift(1) * df['Market_Return']
        df['Cumulative_Market'] = (1 + df['Market_Return'].fillna(0)).cumprod()
        df['Cumulative_Strategy'] = (1 + df['Strategy_Return'].fillna(0)).cumprod()
        
        total_strategy = df['Cumulative_Strategy'].iloc[-1] - 1
        total_market = df['Cumulative_Market'].iloc[-1] - 1
        
        strategy_mean = df['Strategy_Return'].mean()
        strategy_std = df['Strategy_Return'].std()
        sharpe_ratio = (strategy_mean / strategy_std) * (365 ** 0.5) if strategy_std != 0 else 0.0

        rolling_max = df['Cumulative_Strategy'].cummax()
        max_drawdown = ((df['Cumulative_Strategy'] - rolling_max) / rolling_max).min()

        start_date = df.index[0].strftime('%Y-%m-%d')
        end_date = df.index[-1].strftime('%Y-%m-%d')

        return (
            f"Backtest Results: {ticker} | Strategy: {strategy.upper()}\n"
            f"----------------------------------------\n"
            f"Period: {start_date} to {end_date}\n\n"
            f"Performance Metrics:\n"
            f"  • Strategy Return : {total_strategy:.2%} (vs B&H: {total_market:.2%})\n"
            f"  • Sharpe Ratio    : {sharpe_ratio:.2f}\n"
            f"  • Max Drawdown    : {max_drawdown:.2%}\n"
            f"----------------------------------------\n"
            f"Applied Strategy Parameters: {kwargs}") 

    except Exception as e:
        return f"Error during backtest: {str(e)}"
    
def rsi_strategy(df: pd.DataFrame, lower_bound: int = 30, upper_bound: int = 70) -> pd.DataFrame:
    df['RSI'] = df.ta.rsi(length=14)
    df['Position'] = 0
    current_pos = 0
    positions = []
    
    for rsi in df['RSI']:
        if rsi < lower_bound:
            current_pos = 1 
        elif rsi > upper_bound:
            current_pos = 0 
        positions.append(current_pos)
        
    df['Position'] = positions
    return df

if __name__ == "__main__":
    mcp.run()