# -*- coding: utf-8 -*-
import akshare as ak
from datetime import datetime, timedelta

print("=" * 50)
print("A股数据接口测试")
print("=" * 50)

# 测试1：获取单支股票信息
print("\n[测试1] 股票基本信息 (000001 平安银行)")
try:
    df = ak.stock_individual_info_em(symbol="000001")
    print(df)
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试2：获取日线历史数据
print("\n[测试2] 日线历史数据 (000001，近30天)")
try:
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    df = ak.stock_zh_a_hist(symbol="000001", start_date=start, end_date=end, adjust="qfq")
    print(f"列名: {list(df.columns)}")
    print(f"数据条数: {len(df)}")
    print(df.tail(3))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试3：获取实时行情
print("\n[测试3] 实时行情批量查询")
try:
    df = ak.stock_zh_a_spot_em()
    print(f"列名: {list(df.columns)[:10]}...")
    print(f"总股票数: {len(df)}")
    stock = df[df['代码'] == '000001']
    print(stock[['代码', '名称', '最新价', '涨跌幅', '成交量']])
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试4：财务指标 - 使用正确的接口 stock_financial_analysis_indicator_em
print("\n[测试4] 财务指标 (000001)")
try:
    df = ak.stock_financial_analysis_indicator_em(symbol="000001", indicator="按报告期")
    print(f"列名: {list(df.columns)[:10]}...")
    print(f"数据条数: {len(df)}")
    if len(df) > 0:
        print(df.head(2)[['报告日期', '基本每股收益', '净资产收益率(%)', '市盈率(倍)', '市净率(倍)']])
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试5：盈利能力 - 使用正确的接口 stock_profit_sheet_by_yearly_em (按年度)
print("\n[测试5] 盈利能力 (000001 按年度)")
try:
    df = ak.stock_profit_sheet_by_yearly_em(symbol="SH000001")
    print(f"列名: {list(df.columns)[:8]}...")
    print(f"数据条数: {len(df)}")
    if len(df) > 0:
        print(df.head(2)[['报告日期', '营业总收入', '净利润']])
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试6：成长能力 - 使用 stock_growth_analyze_em
print("\n[测试6] 成长能力 (000001)")
try:
    df = ak.stock_growth_analyze_em(symbol="000001", indicator="按报告期")
    print(f"列名: {list(df.columns)}")
    print(f"数据条数: {len(df)}")
    if len(df) > 0:
        print(df.head(2))
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "=" * 50)
print("测试完成")