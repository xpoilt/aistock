import requests
import time
import sqlite3
from pathlib import Path
import random

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
        response = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
        
    except Exception as e:
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
                pass
    
    conn.commit()
    conn.close()
    
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

def random_sleep(min_sec: float = 0.5, max_sec: float = 2.0):
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)

def main():
    init_db()
    
    stock_df = get_all_stock_list()
    if stock_df is None or len(stock_df) == 0:
        print("[ERROR] 未获取到股票列表，退出")
        return
    
    success_count = 0
    fail_count = 0
    total_count = len(stock_df)
    
    print(f"[INFO] 开始批量下载 {total_count} 只股票的数据...")
    print(f"[INFO] 每次请求随机等待 0.5-2.0 秒，失败重试 3 次")
    print("=" * 60)
    
    for idx, row in stock_df.iterrows():
        stock_code = row['code']
        stock_name = row['name']
        
        print(f"[{idx+1}/{total_count}] 正在处理: {stock_code} {stock_name}")
        
        success = False
        for retry in range(3):
            data = get_sse_historical_data(stock_code, "20200101", "20500101")
            
            if data and save_sse_data_to_db(stock_code, data):
                kline_count = len(data.get("kline", []))
                print(f"  [SUCCESS] {stock_code} 成功保存 {kline_count} 条记录")
                success = True
                success_count += 1
                break
            else:
                if retry < 2:
                    print(f"  [RETRY] {stock_code} 等待 2 秒后重试 ({retry + 1}/3)...")
                    time.sleep(2)
        
        if not success:
            print(f"  [FAIL] {stock_code} 获取失败")
            fail_count += 1
        
        if idx < total_count - 1:
            random_sleep(0.5, 2.0)
    
    print("=" * 60)
    print(f"[INFO] 批量下载完成！")
    print(f"[INFO] 成功: {success_count} 只")
    print(f"[INFO] 失败: {fail_count} 只")
    print(f"[INFO] 总计: {total_count} 只")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
