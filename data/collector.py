import akshare as ak
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import sqlite3

class StockCollector:
    def __init__(self, db_path: str = "stock_data.db"):
        self.db_path = db_path
    
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        try:
            if stock_code.startswith('6'):
                symbol = f"sh{stock_code}"
            else:
                symbol = f"sz{stock_code}"
            
            df = ak.stock_individual_info_em(symbol=stock_code)
            info = {}
            for _, row in df.iterrows():
                info[row['item']] = row['value']
            
            return {
                'stock_code': stock_code,
                'stock_name': info.get('股票名称', ''),
                'industry': info.get('行业', ''),
                'market': 'SH' if stock_code.startswith('6') else 'SZ',
                'list_date': info.get('上市时间', '')
            }
        except Exception as e:
            print(f"获取股票 {stock_code} 信息失败: {e}")
            return None
    
    def save_stock_info(self, stock_code: str):
        info = self.get_stock_info(stock_code)
        if info:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_info 
                    (stock_code, stock_name, industry, market, list_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (info['stock_code'], info['stock_name'], 
                      info['industry'], info['market'], info['list_date']))
                conn.commit()
            return True
        return False
    
    def get_daily_price(self, stock_code: str, 
                        start_date: str = None, 
                        end_date: str = None) -> List[Dict]:
        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date, 
                                    end_date=end_date, adjust="qfq")
            
            records = []
            for _, row in df.iterrows():
                records.append({
                    'stock_code': stock_code,
                    'trade_date': row['日期'],
                    'open': row['开盘'],
                    'high': row['最高'],
                    'low': row['最低'],
                    'close': row['收盘'],
                    'volume': row['成交量'],
                    'amount': row['成交额']
                })
            return records
        except Exception as e:
            print(f"获取股票 {stock_code} 日线数据失败: {e}")
            return []
    
    def save_daily_price(self, stock_code: str, 
                         start_date: str = None, 
                         end_date: str = None) -> int:
        records = self.get_daily_price(stock_code, start_date, end_date)
        if not records:
            return 0
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for r in records:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_price 
                    (stock_code, trade_date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (r['stock_code'], r['trade_date'], r['open'], r['high'],
                      r['low'], r['close'], r['volume'], r['amount']))
            conn.commit()
            return len(records)
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict]:
        try:
            df = ak.stock_zh_a_spot_em()
            stock_data = df[df['代码'] == stock_code]
            if stock_data.empty:
                return None
            
            row = stock_data.iloc[0]
            return {
                'stock_code': stock_code,
                'stock_name': row['名称'],
                'open': row['开盘'],
                'high': row['最高'],
                'low': row['最低'],
                'close': row['最新价'],
                'volume': row['成交量'],
                'amount': row['成交额'],
                'change_pct': row['涨跌幅'],
                'change_amount': row['涨跌额']
            }
        except Exception as e:
            print(f"获取股票 {stock_code} 实时行情失败: {e}")
            return None
    
    def get_financial_indicator(self, stock_code: str) -> List[Dict]:
        try:
            df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            
            records = []
            for _, row in df.head(8).iterrows():
                records.append({
                    'stock_code': stock_code,
                    'report_date': str(row.get('日期', '')),
                    'eps': row.get('基本每股收益'),
                    'roe': row.get('净资产收益率(%)'),
                    'pe': row.get('市盈率(倍)'),
                    'pb': row.get('市净率(倍)'),
                    'gross_margin': row.get('销售毛利率(%)'),
                    'net_margin': row.get('销售净利率(%)'),
                    'debt_ratio': row.get('资产负债率(%)'),
                    'current_ratio': row.get('流动比率'),
                    'quick_ratio': row.get('速动比率')
                })
            return records
        except Exception as e:
            print(f"获取股票 {stock_code} 财务指标失败: {e}")
            return []
    
    def save_financial_indicator(self, stock_code: str) -> int:
        records = self.get_financial_indicator(stock_code)
        if not records:
            return 0
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for r in records:
                cursor.execute("""
                    INSERT OR REPLACE INTO financial_indicator 
                    (stock_code, report_date, eps, roe, pe, pb, gross_margin,
                     net_margin, debt_ratio, current_ratio, quick_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (r['stock_code'], r['report_date'], r['eps'], r['roe'],
                      r['pe'], r['pb'], r['gross_margin'], r['net_margin'],
                      r['debt_ratio'], r['current_ratio'], r['quick_ratio']))
            conn.commit()
            return len(records)
    
    def get_profitability(self, stock_code: str) -> List[Dict]:
        try:
            df = ak.stock_profit_sheet_by_report_em(symbol=stock_code)
            
            records = []
            for _, row in df.head(8).iterrows():
                records.append({
                    'stock_code': stock_code,
                    'report_date': str(row.get('报告日期', '')),
                    'operating_income': row.get('营业总收入'),
                    'operating_profit': row.get('营业利润'),
                    'total_profit': row.get('利润总额'),
                    'net_profit': row.get('净利润'),
                    'total_assets': row.get('资产总计'),
                    'total_liabilities': row.get('负债合计')
                })
            return records
        except Exception as e:
            print(f"获取股票 {stock_code} 盈利能力数据失败: {e}")
            return []
    
    def save_profitability(self, stock_code: str) -> int:
        records = self.get_profitability(stock_code)
        if not records:
            return 0
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for r in records:
                cursor.execute("""
                    INSERT OR REPLACE INTO profitability 
                    (stock_code, report_date, operating_income, operating_profit,
                     total_profit, net_profit, total_assets, total_liabilities)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (r['stock_code'], r['report_date'], r['operating_income'],
                      r['operating_profit'], r['total_profit'], r['net_profit'],
                      r['total_assets'], r['total_liabilities']))
            conn.commit()
            return len(records)
    
    def get_growth_ability(self, stock_code: str) -> List[Dict]:
        try:
            df = ak.stock_growth_em(symbol=stock_code)
            
            records = []
            for _, row in df.head(8).iterrows():
                records.append({
                    'stock_code': stock_code,
                    'report_date': str(row.get('报告日期', '')),
                    'revenue_growth': row.get('营收增长率(%)'),
                    'profit_growth': row.get('净利润增长率(%)'),
                    'asset_growth': row.get('资产增长率(%)')
                })
            return records
        except Exception as e:
            print(f"获取股票 {stock_code} 成长能力数据失败: {e}")
            return []
    
    def save_growth_ability(self, stock_code: str) -> int:
        records = self.get_growth_ability(stock_code)
        if not records:
            return 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for r in records:
                cursor.execute("""
                    INSERT OR REPLACE INTO growth_ability 
                    (stock_code, report_date, revenue_growth, profit_growth, asset_growth)
                    VALUES (?, ?, ?, ?, ?)
                """, (r['stock_code'], r['report_date'], r['revenue_growth'],
                      r['profit_growth'], r['asset_growth']))
            conn.commit()
            return len(records)
    
    def save_all_financial_data(self, stock_code: str) -> Dict[str, int]:
        counts = {}
        counts['indicator'] = self.save_financial_indicator(stock_code)
        counts['profitability'] = self.save_profitability(stock_code)
        counts['growth'] = self.save_growth_ability(stock_code)
        return counts