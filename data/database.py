import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
import os

class StockDatabase:
    def __init__(self, db_path: str = "stock_data.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_info (
                    stock_code TEXT PRIMARY KEY,
                    stock_name TEXT NOT NULL,
                    industry TEXT,
                    market TEXT,
                    list_date TEXT
                )
            """)
            
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
                CREATE INDEX IF NOT EXISTS idx_daily_price_stock_date 
                ON daily_price(stock_code, trade_date)
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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profitability (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    operating_income REAL,
                    operating_profit REAL,
                    total_profit REAL,
                    net_profit REAL,
                    total_assets REAL,
                    total_liabilities REAL,
                    UNIQUE(stock_code, report_date)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS growth_ability (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    revenue_growth REAL,
                    profit_growth REAL,
                    asset_growth REAL,
                    UNIQUE(stock_code, report_date)
                )
            """)
            
            conn.commit()
    
    def save_stock_info(self, stock_code: str, stock_name: str, 
                        industry: str = None, market: str = None, 
                        list_date: str = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO stock_info 
                (stock_code, stock_name, industry, market, list_date)
                VALUES (?, ?, ?, ?, ?)
            """, (stock_code, stock_name, industry, market, list_date))
            conn.commit()
    
    def save_daily_price(self, stock_code: str, trade_date: str,
                         open_price: float, high: float, low: float,
                         close: float, volume: float, amount: float):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO daily_price 
                (stock_code, trade_date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, trade_date, open_price, high, low, close, volume, amount))
            conn.commit()
    
    def save_financial_indicator(self, stock_code: str, report_date: str,
                                  eps: float = None, roe: float = None,
                                  pe: float = None, pb: float = None,
                                  gross_margin: float = None, net_margin: float = None,
                                  debt_ratio: float = None, current_ratio: float = None,
                                  quick_ratio: float = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO financial_indicator 
                (stock_code, report_date, eps, roe, pe, pb, gross_margin, 
                 net_margin, debt_ratio, current_ratio, quick_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, report_date, eps, roe, pe, pb, gross_margin,
                  net_margin, debt_ratio, current_ratio, quick_ratio))
            conn.commit()
    
    def save_profitability(self, stock_code: str, report_date: str,
                           operating_income: float = None,
                           operating_profit: float = None,
                           total_profit: float = None,
                           net_profit: float = None,
                           total_assets: float = None,
                           total_liabilities: float = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO profitability 
                (stock_code, report_date, operating_income, operating_profit,
                 total_profit, net_profit, total_assets, total_liabilities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, report_date, operating_income, operating_profit,
                  total_profit, net_profit, total_assets, total_liabilities))
            conn.commit()
    
    def save_growth_ability(self, stock_code: str, report_date: str,
                            revenue_growth: float = None,
                            profit_growth: float = None,
                            asset_growth: float = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO growth_ability 
                (stock_code, report_date, revenue_growth, profit_growth, asset_growth)
                VALUES (?, ?, ?, ?, ?)
            """, (stock_code, report_date, revenue_growth, profit_growth, asset_growth))
            conn.commit()
    
    def get_daily_price(self, stock_code: str, 
                        start_date: str = None, 
                        end_date: str = None) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if start_date and end_date:
                cursor.execute("""
                    SELECT trade_date, open, high, low, close, volume, amount
                    FROM daily_price
                    WHERE stock_code = ? AND trade_date BETWEEN ? AND ?
                    ORDER BY trade_date
                """, (stock_code, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT trade_date, open, high, low, close, volume, amount
                    FROM daily_price
                    WHERE stock_code = ?
                    ORDER BY trade_date
                """, (stock_code,))
            return cursor.fetchall()
    
    def get_latest_price(self, stock_code: str) -> Optional[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT trade_date, open, high, low, close, volume, amount
                FROM daily_price
                WHERE stock_code = ?
                ORDER BY trade_date DESC
                LIMIT 1
            """, (stock_code,))
            return cursor.fetchone()
    
    def get_all_stocks(self) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stock_code, stock_name FROM stock_info")
            return cursor.fetchall()
    
    def get_financial_indicator(self, stock_code: str) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_date, eps, roe, pe, pb, gross_margin, 
                       net_margin, debt_ratio, current_ratio, quick_ratio
                FROM financial_indicator
                WHERE stock_code = ?
                ORDER BY report_date DESC
            """, (stock_code,))
            return cursor.fetchall()
    
    def get_profitability(self, stock_code: str) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_date, operating_income, operating_profit,
                       total_profit, net_profit, total_assets, total_liabilities
                FROM profitability
                WHERE stock_code = ?
                ORDER BY report_date DESC
            """, (stock_code,))
            return cursor.fetchall()
    
    def get_growth_ability(self, stock_code: str) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_date, revenue_growth, profit_growth, asset_growth
                FROM growth_ability
                WHERE stock_code = ?
                ORDER BY report_date DESC
            """, (stock_code,))
            return cursor.fetchall()