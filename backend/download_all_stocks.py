import asyncio
import sqlite3
import time
import os
from pathlib import Path

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

def fetch_and_save_stock_data(stock_code: str, max_retries: int = 3):
    import sqlite3
    
    conn = sqlite3.connect(str(STOCK_DB))
    cursor = conn.cursor()
    
    import akshare as ak
    
    for retry in range(max_retries):
        try:
            print(f"[INFO] 正在获取 {stock_code} 的数据... (尝试 {retry + 1}/{max_retries})")
            
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20200101", end_date="20500101", adjust="")
            
            if df is not None and len(df) > 0:
                print(f"[INFO] {stock_code} 成功获取 {len(df)} 条记录")
                
                for _, row in df.iterrows():
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO daily_price (stock_code, trade_date, open, high, low, close, volume, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (stock_code, str(row['日期']), float(row['开盘']), float(row['最高']), float(row['最低']), 
                              float(row['收盘']), float(row['成交量']), float(row['成交额'])))
                    except Exception as e:
                        print(f"[WARN] {stock_code} 保存数据失败: {e}")
                conn.commit()
                conn.close()
                return True
            else:
                print(f"[WARN] {stock_code} 未获取到数据")
                if retry < max_retries - 1:
                    print(f"[INFO] {stock_code} 等待 2 秒后重试...")
                    time.sleep(2)
                continue
        except Exception as e:
            print(f"[ERROR] {stock_code} 获取失败 (尝试 {retry + 1}/{max_retries}): {e}")
            if retry < max_retries - 1:
                print(f"[INFO] {stock_code} 等待 3 秒后重试...")
                time.sleep(3)
            continue
    
    conn.close()
    return False

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
    print(f"[INFO] 每个请求间隔 1 秒，失败重试 3 次")
    print("=" * 60)
    
    for idx, row in stock_df.iterrows():
        stock_code = row['code']
        stock_name = row['name']
        
        print(f"[{idx+1}/{total_count}] 正在处理: {stock_code} {stock_name}")
        
        success = fetch_and_save_stock_data(stock_code)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
        
        if idx < total_count - 1:
            time.sleep(1)
    
    print("=" * 60)
    print(f"[INFO] 批量下载完成！")
    print(f"[INFO] 成功: {success_count} 只")
    print(f"[INFO] 失败: {fail_count} 只")
    print(f"[INFO] 总计: {total_count} 只")

if __name__ == "__main__":
    main()
