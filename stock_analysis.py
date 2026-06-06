import yfinance as yf
import pandas as pd
import os
from datetime import datetime

stock_list_str = os.getenv('STOCK_LIST', '0700.HK, BABA, 600519.SS')
stock_list = [s.strip() for s in stock_list_str.split(',')]

results = []
for symbol in stock_list:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1d')
        if not hist.empty:
            close = hist['Close'].iloc[-1]
            results.append({'股票代码': symbol, '收盘价': round(close, 2)})
        else:
            results.append({'股票代码': symbol, '收盘价': '无数据'})
    except Exception as e:
        results.append({'股票代码': symbol, '收盘价': f'错误: {str(e)}'})

df = pd.DataFrame(results)
df.to_csv('report.csv', index=False, encoding='utf-8')
print(f"分析完成时间: {datetime.now()}")
print(df.to_string())
