import requests
import time
import sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd

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

def get_sse_stock_info(stock_code: str):
    url = f"https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE={stock_code}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.sse.com.cn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    
    try:
        print(f"[INFO] 正在请求: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        print(f"[INFO] 状态码: {response.status_code}")
        print(f"[INFO] 响应长度: {len(response.text)}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"\n[INFO] 页面标题: {soup.title.string if soup.title else '无标题'}")
        
        print(f"\n[INFO] 查找表格...")
        tables = soup.find_all('table')
        print(f"[INFO] 找到 {len(tables)} 个表格")
        
        for idx, table in enumerate(tables):
            print(f"\n[INFO] 表格 {idx + 1}:")
            print(table.get_text()[:500])
        
        return response.text
        
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}")
        return None

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
    print("测试爬取上交所数据")
    print("=" * 60)
    
    test_code = "600000"
    html = get_sse_stock_info(test_code)
    
    if html:
        print("\n" + "=" * 60)
        print("HTML 已获取，正在保存到文件...")
        with open("sse_test.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("已保存到 sse_test.html")
        print("请打开该文件查看页面结构")

if __name__ == "__main__":
    main()
