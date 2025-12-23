import yfinance as yf
import pandas as pd
from datetime import datetime

tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD']
start_date = '2024-01-01'
end_date = datetime.now().strftime('%Y-%m-%d')

print(f"Downloading ({start_date} ~ {end_date})...")

all_data = []
for ticker in tickers:
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.reset_index()
    symbol = ticker.split('-')[0]
    df['symbol'] = symbol

    cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = df[cols]
    
    all_data.append(df)
    print(f"{symbol} downloaded, including {len(df)} rows.")

final_df = pd.concat(all_data)
final_df['Date'] = final_df['Date'].dt.strftime('%Y-%m-%d')

output_path = "data/real_crypto_2024.csv"
final_df.to_csv(output_path, index=False)

print(f"\nDownload success, data saved in: {output_path}")
print("Columns are:", list(final_df.columns))