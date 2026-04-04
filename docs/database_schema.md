# 数据库表结构文档

## 概述

本项目使用 SQLite 数据库存储 A 股股票数据，数据库文件默认为 `stock_data.db`。

---

## 数据表结构

### 1. stock_info (股票基础信息表)

存储股票的基本信息，每支股票一条记录。

| 字段 | 类型 | 说明 | 主键 |
|------|------|------|------|
| stock_code | TEXT | 股票代码 (如 000001) | ✅ |
| stock_name | TEXT | 股票名称 | |
| industry | TEXT | 所属行业 | |
| market | TEXT | 交易所 (SH/SZ) | |
| list_date | TEXT | 上市日期 (YYYYMMDD) | |

**说明**: 股票代码为主键，确保每支股票唯一一条记录。

---

### 2. daily_price (日线行情表)

存储股票的每日行情数据，支持历史数据长期存储。

| 字段 | 类型 | 说明 | 主键 |
|------|------|------|------|
| id | INTEGER | 自增ID | ✅ |
| stock_code | TEXT | 股票代码 | |
| trade_date | TEXT | 交易日期 (YYYY-MM-DD) | |
| open | REAL | 开盘价 (元) | |
| high | REAL | 最高价 (元) | |
| low | REAL | 最低价 (元) | |
| close | REAL | 收盘价 (元) | |
| volume | REAL | 成交量 (股) | |
| amount | REAL | 成交额 (元) | |

**索引**: `idx_daily_price_stock_date` ON (stock_code, trade_date)

**唯一约束**: (stock_code, trade_date) - 同一股票同一日期只有一条记录

**更新策略**: 使用 `INSERT OR REPLACE`，重复日期自动覆盖

---

### 3. financial_indicator (财务指标表)

存储股票的财务指标数据，按报告期存储。

| 字段 | 类型 | 说明 | 主键 |
|------|------|------|------|
| id | INTEGER | 自增ID | ✅ |
| stock_code | TEXT | 股票代码 | |
| report_date | TEXT | 报告期 (YYYY-MM-DD) | |
| eps | REAL | 基本每股收益 (元) | |
| roe | REAL | 净资产收益率 (%) | |
| pe | REAL | 市盈率 (倍) | |
| pb | REAL | 市净率 (倍) | |
| gross_margin | REAL | 销售毛利率 (%) | |
| net_margin | REAL | 销售净利率 (%) | |
| debt_ratio | REAL | 资产负债率 (%) | |
| current_ratio | REAL | 流动比率 | |
| quick_ratio | REAL | 速动比率 | |

**唯一约束**: (stock_code, report_date)

---

### 4. profitability (盈利能力表)

存储股票的利润表数据，按报告期存储。

| 字段 | 类型 | 说明 | 主键 |
|------|------|------|------|
| id | INTEGER | 自增ID | ✅ |
| stock_code | TEXT | 股票代码 | |
| report_date | TEXT | 报告期 (YYYY-MM-DD) | |
| operating_income | REAL | 营业总收入 (元) | |
| operating_profit | REAL | 营业利润 (元) | |
| total_profit | REAL | 利润总额 (元) | |
| net_profit | REAL | 净利润 (元) | |
| total_assets | REAL | 总资产 (元) | |
| total_liabilities | REAL | 总负债 (元) | |

**唯一约束**: (stock_code, report_date)

---

### 5. growth_ability (成长能力表)

存储股票的成长性指标，按报告期存储。

| 字段 | 类型 | 说明 | 主键 |
|------|------|------|------|
| id | INTEGER | 自增ID | ✅ |
| stock_code | TEXT | 股票代码 | |
| report_date | TEXT | 报告期 (YYYY-MM-DD) | |
| revenue_growth | REAL | 营收增长率 (%) | |
| profit_growth | REAL | 净利润增长率 (%) | |
| asset_growth | REAL | 资产增长率 (%) | |

**唯一约束**: (stock_code, report_date)

---

## 表关系图
┌─────────────────────────────────────────────────────────────┐
│                     stock_info                               │
│  股票代码(主键) | 股票名称 | 行业 | 交易所 | 上市日期        │
└─────────────────────────────────────────────────────────────┘
│
┌─────────────────────┼─────────────────────┐
│                     │                     │
▼                     ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   daily_price     │ │financial_indicator│ │   profitability   │
│   日线行情表       │ │   财务指标表        │ │   盈利能力表        │
├───────────────────┤ ├───────────────────┤ ├───────────────────┤
│ stock_code        │ │ stock_code        │ │ stock_code        │
│ trade_date       │ │ report_date       │ │ report_date       │
│ open/high/low/   │ │ eps/roe/pe/pb/    │ │ operating_income/ │
│ close/volume/    │ │ gross_margin/      │ │ operating_profit/ │
│ amount           │ │ net_margin/...    │ │ total_profit/...  │
└───────────────────┘ └───────────────────┘ └───────────────────┘
│
▼
┌───────────────────┐
│  growth_ability   │
│   成长能力表        │
├───────────────────┤
│ stock_code        │
│ report_date       │
│ revenue_growth/   │
│ profit_growth/    │
│ asset_growth      │
└───────────────────┘


---

## 数据更新策略

| 表名 | 更新方式 | 说明 |
|------|----------|------|
| stock_info | INSERT OR REPLACE | 股票信息变更时覆盖更新 |
| daily_price | INSERT OR REPLACE | 同一日期数据自动覆盖 |
| financial_indicator | INSERT OR REPLACE | 新报告期追加，旧数据保留 |
| profitability | INSERT OR REPLACE | 新报告期追加，旧数据保留 |
| growth_ability | INSERT OR REPLACE | 新报告期追加，旧数据保留 |

---

## 使用示例

### 查询某股票的历史行情

```python
from data.database import StockDatabase

db = StockDatabase()
prices = db.get_daily_price("000001", "2025-01-01", "2026-01-01")
for row in prices:
    print(f"日期: {row[0]}, 收盘价: {row[5]}")
```

### 查询某股票的财务数据

```python
# 财务指标
indicators = db.get_financial_indicator("000001")

# 盈利能力
profits = db.get_profitability("000001")

# 成长能力
growth = db.get_growth_ability("000001")
```

---

*最后更新: 2026-04-04*
