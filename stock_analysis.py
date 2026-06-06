import yfinance as yf
import pandas as pd
import os
from datetime import datetime
from openai import OpenAI
import akshare as ak

# ---------- 配置 ----------
STOCK_LIST_STR = os.getenv('STOCK_LIST', '002015.SZ, 000681.SZ, 603990.SS, 002137.SZ')
STOCK_LIST = [s.strip() for s in STOCK_LIST_STR.split(',')]

# 主要指数
INDEX_LIST = {
    '上证指数': '000001.SS',
    '深证成指': '399001.SZ',
    '创业板指': '399006.SZ'
}

# ---------- 自动获取股票中文名称（使用全市场快照缓存）----------
_name_cache = None

def get_stock_name(symbol):
    global _name_cache
    code = symbol.split('.')[0]
    
    if _name_cache is None:
        try:
            print("正在加载全市场股票名称缓存...")
            spot = ak.stock_zh_a_spot()
            _name_cache = dict(zip(spot['代码'], spot['名称']))
            print(f"缓存加载完成，共 {len(_name_cache)} 只股票")
        except Exception as e:
            print(f"全市场快照加载失败: {e}")
            _name_cache = {}
    
    if code in _name_cache:
        return _name_cache[code]
    
    # 备用：个股信息接口
    try:
        info = ak.stock_individual_info_em(symbol=code)
        name = info[info['item'] == '股票简称']['value'].values[0]
        _name_cache[code] = name
        return name
    except Exception as e:
        print(f"备用接口获取名称失败 {code}: {e}")
        # 最后回退到代码本身
        return code

# ---------- 获取大盘指数 ----------
def get_index_data():
    index_text = "【大盘指数】\n"
    for name, symbol in INDEX_LIST.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='2d')
            if len(hist) >= 2:
                close_today = hist['Close'].iloc[-1]
                close_yest = hist['Close'].iloc[-2]
                change_pct = (close_today - close_yest) / close_yest * 100
                volume = hist['Volume'].iloc[-1]
                index_text += f"{name}: {close_today:.2f} ({change_pct:+.2f}%), 成交量:{volume/1e8:.2f}亿\n"
            else:
                index_text += f"{name}: 数据不足\n"
        except:
            index_text += f"{name}: 获取失败\n"
    return index_text

# ---------- 获取个股数据 ----------
def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='2d')
        if len(hist) < 2:
            return None, None, None
        close_today = hist['Close'].iloc[-1]
        close_yest = hist['Close'].iloc[-2]
        change_pct = (close_today - close_yest) / close_yest * 100
        volume = hist['Volume'].iloc[-1]
        return close_today, change_pct, volume
    except Exception:
        return None, None, None

# ---------- AI 分析 ----------
def call_deepseek_for_analysis(stock_name, symbol, close, change_pct, volume, index_info):
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return "AI分析失败: 未配置 DEEPSEEK_API_KEY"
    
    prompt = f"""你是A股短线交易专家。根据以下提供的个股数据和大盘情况，给出操作建议。

【个股数据】
股票名称: {stock_name} (代码: {symbol})
最新收盘价: {close:.2f}
涨跌幅: {change_pct:+.2f}%
成交量: {int(volume)} 股

【大盘情绪】
{index_info}

请严格按照以下格式输出（每个字段必须存在，不要有多余解释）：
- 次日预测区间: [最低价-最高价，基于波动率估算]
- 支撑位: [价格]
- 压力位: [价格]
- 建议买入区间: [xx - xx]
- 建议卖出区间: [xx - xx]
- 合理仓位: [例如 1-2成]
- 止盈点位: [价格]
- 止损点位: [价格]
- 短线操作建议: [买入/观望/卖出]
- 趋势判断: [上升/震荡/下降]
- 一句话总结: [不超过30字]
"""
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是经验丰富的股票分析师，输出简洁、数据驱动、可操作。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI调用失败: {str(e)}"

# ---------- 主流程 ----------
def main():
    index_info = get_index_data()
    results = []
    full_report = f"AI股票分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{index_info}\n"
    
    for symbol in STOCK_LIST:
        print(f"处理 {symbol}...")
        stock_name = get_stock_name(symbol)
        close, change_pct, volume = get_stock_data(symbol)
        if close is None:
            results.append({'股票名称': stock_name, '代码': symbol, '错误': '数据获取失败'})
            full_report += f"\n## {stock_name} ({symbol})\n错误: 数据获取失败\n"
            continue
        
        ai_analysis = call_deepseek_for_analysis(stock_name, symbol, close, change_pct, volume, index_info)
        
        results.append({
            '股票名称': stock_name,
            '代码': symbol,
            '收盘价': round(close, 2),
            '涨跌幅(%)': round(change_pct, 2),
            'AI分析': ai_analysis
        })
        full_report += f"\n## {stock_name} ({symbol})\n{ai_analysis}\n"
    
    df = pd.DataFrame(results)
    df.to_csv('report.csv', index=False, encoding='utf-8-sig')
    with open('analysis_report.txt', 'w', encoding='utf-8') as f:
        f.write(full_report)
    
    print("报告已生成。")
    print(full_report)

if __name__ == "__main__":
    main()
