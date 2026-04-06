import requests
import time
import sqlite3
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
STOCK_DB = BASE_DIR / "stock_data.db"

def init_db():
    conn = sqlite3.connect(str(STOCK_DB))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_price (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            UNIQUE(stock_code, trade_date)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_indicator (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            report_date TEXT NOT NULL,
            eps REAL,
            roe REAL,
            pe REAL,
            pb REAL,
            gross_margin REAL,
            net_margin REAL,
            debt_ratio REAL,
            current_ratio REAL,
            quick_ratio REAL,
            UNIQUE(stock_code, report_date)
        )
    """)
    
    conn.commit()
    conn.close()

def get_sse_historical_data(stock_code: str, begin_date: str = "20200101", end_date: str = "20500101"):
    url = f"http://yunhq.sse.com.cn:32041/v1/sh1/dayk/{stock_code}"
    
    params = {
        "begin": begin_date,
        "end": end_date,
        "select": "date,open,high,low,close,volume,amount"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.sse.com.cn/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://www.sse.com.cn"
    }
    
    try:
        print(f"[INFO] 正在请求: {url}")
        print(f"[INFO] 参数: {params}")
        
        response = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
        
        print(f"[INFO] 状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[INFO] 解析成功，总共 {len(data.get('kline', []))} 条记录")
            return data
        else:
            print(f"[ERROR] 请求失败: {response.status_code}")
            return None
        
    except Exception as e:
        print(f"[ERROR] 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_sse_data_to_db(stock_code: str, data):
    if not data or "kline" not in data:
        return False
    
    conn = sqlite3.connect(str(STOCK_DB))
    cursor = conn.cursor()
    
    kline_data = data.get("kline", [])
    success_count = 0
    
    for item in kline_data:
        if len(item) >= 7:
            date_int = item[0]
            open_price = item[1]
            high = item[2]
            low = item[3]
            close = item[4]
            volume = item[5]
            amount = item[6]
            
            trade_date = str(date_int)
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_price (stock_code, trade_date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (stock_code, trade_date, open_price, high, low, close, volume, amount))
                success_count += 1
            except Exception as e:
                print(f"[WARN] 保存 {stock_code} {trade_date} 失败: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"[INFO] {stock_code} 成功保存 {success_count} 条记录")
    return success_count > 0

def get_all_stock_list():
    import akshare as ak
    
    print("[INFO] 正在获取A股股票列表...")
    try:
        df = ak.stock_info_a_code_name()
        print(f"[INFO] 共获取到 {len(df)} 只股票")
        return df
    except Exception as e:
        print(f"[ERROR] 获取股票列表失败: {e}")
        return None

def main():
    init_db()
    
    print("=" * 60)
    print("测试上交所历史数据接口")
    print("=" * 60)
    
    test_code = "600000"
    data = get_sse_historical_data(test_code, "20240101", "20250101")
    
    if data:
        print("\n" + "=" * 60)
        print("数据获取成功！正在保存到数据库...")
        print("=" * 60)
        
        save_sse_data_to_db(test_code, data)
        
        kline_data = data.get("kline", [])
        print(f"\n共 {len(kline_data)} 条数据")
        
        for i in range(min(5, len(kline_data))):
            item = kline_data[i]
            print(f"{i+1}. 日期: {item[0]}, 开盘: {item[1]}, 最高: {item[2]}, 最低: {item[3]}, 收盘: {item[4]}, 成交量: {item[5]}, 成交额: {item[6]}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
