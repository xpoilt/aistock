from data.collector import StockCollector
from data.database import StockDatabase
import akshare as ak

def main():
    db = StockDatabase()
    collector = StockCollector()
    
    print("=" * 50)
    print("A股数据采集工具")
    print("=" * 50)
    print("1. 采集单支股票历史数据（日线+财务）")
    print("2. 采集全部A股列表")
    print("3. 获取单支股票实时行情")
    print("4. 查看数据库中的股票")
    print("5. 查看股票财务数据")
    print("6. 退出")
    print("=" * 50)
    
    while True:
        choice = input("\n请选择功能 (1-6): ").strip()
        
        if choice == '1':
            stock_code = input("请输入股票代码 (如 000001): ").strip()
            if stock_code:
                print(f"\n正在采集 {stock_code} 的数据...")
                
                print("  [1/5] 保存股票信息...")
                collector.save_stock_info(stock_code)
                
                print("  [2/5] 保存日线数据...")
                count = collector.save_daily_price(stock_code)
                print(f"       已保存 {count} 条日线数据")
                
                print("  [3/5] 保存财务指标...")
                indicator_count = collector.save_financial_indicator(stock_code)
                print(f"       已保存 {indicator_count} 条财务指标")
                
                print("  [4/5] 保存盈利能力...")
                profit_count = collector.save_profitability(stock_code)
                print(f"       已保存 {profit_count} 条盈利数据")
                
                print("  [5/5] 保存成长能力...")
                growth_count = collector.save_growth_ability(stock_code)
                print(f"       已保存 {growth_count} 条成长数据")
                
                print("\n采集完成!")
        
        elif choice == '2':
            print("\n正在获取A股列表...")
            try:
                df = ak.stock_zh_a_spot_em()
                stocks = df[['代码', '名称']].values.tolist()
                print(f"  - 共获取 {len(stocks)} 支股票")
                
                for i, (code, name) in enumerate(stocks):
                    collector.save_stock_info(code)
                    if (i + 1) % 100 == 0:
                        print(f"  - 已处理 {i + 1}/{len(stocks)}")
                print(f"  - 完成！共处理 {len(stocks)} 支股票")
            except Exception as e:
                print(f"获取失败: {e}")
        
        elif choice == '3':
            stock_code = input("请输入股票代码 (如 000001): ").strip()
            if stock_code:
                print(f"\n正在获取 {stock_code} 实时行情...")
                quote = collector.get_realtime_quote(stock_code)
                if quote:
                    print(f"\n股票名称: {quote['stock_name']}")
                    print(f"最新价: {quote['close']}")
                    print(f"涨跌幅: {quote['change_pct']}%")
                    print(f"涨跌额: {quote['change_amount']}")
                    print(f"最高价: {quote['high']}")
                    print(f"最低价: {quote['low']}")
                    print(f"成交量: {quote['volume']}")
                    print(f"成交额: {quote['amount']}")
                else:
                    print("获取失败")
        
        elif choice == '4':
            stocks = db.get_all_stocks()
            print(f"\n数据库中共 {len(stocks)} 支股票:")
            for code, name in stocks[:20]:
                print(f"  {code} - {name}")
            if len(stocks) > 20:
                print(f"  ... 还有 {len(stocks) - 20} 支")
        
        elif choice == '5':
            stock_code = input("请输入股票代码 (如 000001): ").strip()
            if stock_code:
                print(f"\n=== 财务指标 ===")
                indicators = db.get_financial_indicator(stock_code)
                for row in indicators[:4]:
                    print(f"  报告期: {row[0]}, EPS: {row[1]}, ROE: {row[2]}%, PE: {row[3]}, PB: {row[4]}")
                    print(f"         毛利率: {row[5]}%, 净利率: {row[6]}%, 资产负债率: {row[7]}%")
                
                print(f"\n=== 盈利能力 ===")
                profits = db.get_profitability(stock_code)
                for row in profits[:4]:
                    print(f"  报告期: {row[0]}, 营收: {row[1]}, 净利润: {row[4]}")
                
                print(f"\n=== 成长能力 ===")
                growth = db.get_growth_ability(stock_code)
                for row in growth[:4]:
                    print(f"  报告期: {row[0]}, 营收增长: {row[1]}%, 利润增长: {row[2]}%, 资产增长: {row[3]}%")
        
        elif choice == '6':
            print("\n再见!")
            break

if __name__ == "__main__":
    main()