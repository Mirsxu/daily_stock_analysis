import yfinance as yf
import pandas as pd
import os
import requests
import json
from datetime import datetime

# ---------- AI 调用函数（使用 DeepSeek API）----------
def call_deepseek(prompt):
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return "错误：未设置 DEEPSEEK_API_KEY 环境变量"
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一名A股短线交易分析师，根据给出的股票数据给出简明趋势判断和操作建议。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"AI调用失败: {str(e)}"

# ---------- 主程序 ----------
# 从环境变量读取股票列表（支持A股后缀 .SZ / .SS）
stock_list_str = os.getenv('STOCK_LIST', '002015.SZ, 000681.SZ, 603990.SS, 002137.SZ')
stock_list = [s.strip() for s in stock_list_str.split(',')]

results = []
full_report = ""

for symbol in stock_list:
    print(f"处理 {symbol}...")
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if len(hist) < 2:
            results.append({"股票代码": symbol, "收盘价": "数据不足", "涨跌幅(%)": "N/A", "AI分析": "无历史数据"})
            full_report += f"\n## {symbol}\n数据不足，无法分析。"
            continue
        
        # 计算涨跌幅
        close_today = hist['Close'].iloc[-1]
        close_yesterday = hist['Close'].iloc[-2]
        change_pct = (close_today - close_yesterday) / close_yesterday * 100
        
        # 构造发给AI的提示词
        price_data = hist[['Open', 'High', 'Low', 'Close', 'Volume']].tail(3).to_string()
        prompt = f"""
股票代码: {symbol}
最近3日数据:
{price_data}

请分析该股票的短线走势，给出以下内容（不要多余的解释）：
- 趋势判断（上升/下降/震荡）
- 短线操作建议（买入/持有/卖出/观望）
- 关键点位（支撑位/压力位）
- 一句话总结
"""
        ai_analysis = call_deepseek(prompt)
        
        results.append({
            "股票代码": symbol,
            "收盘价": round(close_today, 2),
            "涨跌幅(%)": round(change_pct, 2),
            "AI分析": ai_analysis
        })
        full_report += f"\n## {symbol}\n{ai_analysis}\n"
    
    except Exception as e:
        results.append({"股票代码": symbol, "收盘价": "错误", "涨跌幅(%)": "错误", "AI分析": str(e)})
        full_report += f"\n## {symbol}\n处理出错: {str(e)}\n"

# 保存 CSV 报告
df = pd.DataFrame(results)
df.to_csv("report.csv", index=False, encoding="utf-8-sig")

# 保存文本报告供钉钉发送
with open("analysis_report.txt", "w", encoding="utf-8") as f:
    f.write(f"AI股票分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{full_report}")

print("报告已生成。")
print(full_report)
