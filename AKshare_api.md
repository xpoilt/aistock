# AKShare API 使用文档

## 概述

AKShare 是一款基于 Python 的开源金融数据接口库，专为个人投资者、量化爱好者、财经数据分析人员打造。

**官网**: https://akshare.akfamily.xyz/
**版本**: 当前使用版本请运行 `ak.__version__` 查看

---

## 数据源

| 数据源 | 占比 | 特点 |
|--------|------|------|
| 新浪财经 | 高 | 实时性好，免费接口 |
| 东方财富 | 高 | 数据全面，权威可靠 |
| Tushare | 中 | 需要积分权限 |
| Yahoo Finance | 低 | 美股/港股数据 |

---

## 接口限制 (Rate Limit)

### 各数据源频率限制

| 数据源 | 建议频率 | 说明 |
|--------|----------|------|
| 新浪财经 | ≤5次/秒/IP | 超出可能触发IP封锁 |
| 东方财富 | ≤3次/秒/IP | 部分接口需要Token签名 |
| Tushare Pro | 依权限等级 | 免费用户低频，需要Token认证 |
| Yahoo Finance | ≤2次/秒/IP | User-Agent检测 |

### 批量请求限制

- **单次最大股票数量**: 100只（经验值）
- 超出可能触发反爬机制或IP封禁

### 频率控制建议

### 超出限制的症状

- 返回空数据（None 或空 DataFrame）
- HTTP 状态码 403 Forbidden
- 响应头包含 `Access Denied` 或 `Request frequency limited`

---

## 本项目使用的接口

### 1. 股票基本信息

**接口**: `ak.stock_individual_info_em(symbol="股票代码")`

```python
df = ak.stock_individual_info_em(symbol="000001")
# 返回字段: item, value
# 示例: 股票代码、股票简称、总股本、流通股、总市值、流通市值、行业、上市时间
```

**返回字段说明**:

| 字段 | 说明 |
|------|------|
| 股票代码 | 6位数字代码 |
| 股票简称 | 中文简称 |
| 总股本 | 总股本数量 |
| 流通股 | 流通股本数量 |
| 总市值 | 总市值（元） |
| 流通市值 | 流通市值（元） |
| 行业 | 所属行业分类 |
| 上市时间 | 格式：YYYYMMDD |

---

### 2. 日线历史数据

**接口**: `ak.stock_zh_a_hist(symbol, start_date, end_date, adjust)`

```python
df = ak.stock_zh_a_hist(
    symbol="000001",
    start_date="20250101",
    end_date="20260101",
    adjust="qfq"  # 前复权
)
```

**参数说明**:

| 参数 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| symbol | str | 股票代码 | 6位数字，如 "000001" |
| start_date | str | 开始日期 | 8位数字，格式 YYYYMMDD |
| end_date | str | 结束日期 | 8位数字，格式 YYYYMMDD |
| adjust | str | 复权方式 | "qfq"(前复权), "hfq"(后复权), ""(不复权) |

**返回字段**:

| 字段 | 说明 |
|------|------|
| 日期 | 交易日期，格式 YYYY-MM-DD |
| 股票代码 | 6位数字代码 |
| 开盘 | 开盘价（元） |
| 收盘 | 收盘价（元） |
| 最高 | 最高价（元） |
| 最低 | 最低价（元） |
| 成交量 | 成交量（股） |
| 成交额 | 成交额（元） |
| 振幅 | 振幅（%） |
| 涨跌幅 | 涨跌幅（%） |
| 涨跌额 | 涨跌额（元） |
| 换手率 | 换手率（%） |

---

### 3. 实时行情（批量）

**接口**: `ak.stock_zh_a_spot_em()`

```python
df = ak.stock_zh_a_spot_em()
# 返回全市场所有股票实时行情
```

**返回字段（部分）**:

| 字段 | 说明 |
|------|------|
| 序号 | 顺序号 |
| 代码 | 6位股票代码 |
| 名称 | 股票中文名称 |
| 最新价 | 当前价格（元） |
| 涨跌幅 | 涨跌幅（%） |
| 涨跌额 | 涨跌额（元） |
| 成交量 | 成交量（股） |
| 成交额 | 成交额（元） |
| 振幅 | 振幅（%） |
| 最高 | 最高价（元） |
| 最低 | 最低价（元） |
| 今开 | 今日开盘价（元） |
| 昨收 | 昨日收盘价（元） |
| 量比 | 量比指标 |
| 换手率 | 换手率（%） |
| 市盈率 | PE（倍） |
| 市净率 | PB（倍） |
| 总市值 | 总市值（元） |
| 流通市值 | 流通市值（元） |

---

### 4. 财务指标

**接口**: `ak.stock_financial_analysis_indicator_em(symbol, indicator)`

```python
df = ak.stock_financial_analysis_indicator_em(
    symbol="000001",
    indicator="按报告期"
)
```

**参数说明**:

| 参数 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| symbol | str | 股票代码 | 6位数字 |
| indicator | str | 指标类型 | "按报告期", "按单季度" |

**返回字段（部分）**:

| 字段 | 说明 |
|------|------|
| 报告日期 | 财报发布日期 |
| 基本每股收益 | EPS（元） |
| 净资产收益率(%) | ROE（%） |
| 市盈率(倍) | PE（倍） |
| 市净率(倍) | PB（倍） |
| 销售毛利率(%) | 毛利率（%） |
| 销售净利率(%) | 净利率（%） |
| 资产负债率(%) | 资产负债率（%） |
| 流动比率 | 流动比率 |
| 速动比率 | 速动比率 |

---

### 5. 盈利能力（利润表）

**接口**: `ak.stock_profit_sheet_by_yearly_em(symbol)`

```python
df = ak.stock_profit_sheet_by_yearly_em(symbol="SH000001")
# 注意：需要加 "SH" 或 "SZ" 前缀
```

**参数**: symbol 格式为 "SH600519" 或 "SZ000001"

**返回字段（部分）**:

| 字段 | 说明 |
|------|------|
| 报告日期 | 财报发布日期 |
| 营业总收入 | 营业收入（元） |
| 营业利润 | 营业利润（元） |
| 利润总额 | 利润总额（元） |
| 净利润 | 净利润（元） |
| 资产总计 | 总资产（元） |
| 负债合计 | 总负债（元） |

---

### 6. 成长能力

**接口**: `ak.stock_growth_analyze_em(symbol, indicator)`

```python
df = ak.stock_growth_analyze_em(
    symbol="000001",
    indicator="按报告期"
)
```

**返回字段（部分）**:

| 字段 | 说明 |
|------|------|
| 报告日期 | 财报发布日期 |
| 营收增长率(%) | 营业收入同比增长率 |
| 净利润增长率(%) | 净利润同比增长率 |
| 资产增长率(%) | 总资产同比增长率 |

---

## 使用建议

### 1. 请求频率控制

```python
import time

def fetch_with_rate_limit(func, *args, **kwargs):
    """带频率控制的获取函数"""
    result = func(*args, **kwargs)
    time.sleep(0.5)  # 间隔0.5秒
    return result
```

### 2. 本地缓存策略

```python
import os
import pickle
from functools import lru_cache

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def cached_fetch(filename, fetch_func, *args, **kwargs):
    """本地缓存获取"""
    filepath = os.path.join(CACHE_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    result = fetch_func(*args, **kwargs)
    with open(filepath, 'wb') as f:
        pickle.dump(result, f)
    return result
```

### 3. 错误处理与重试

```python
import time
from typing import Callable, Any

def retry_fetch(func: Callable, max_retries: int = 3, delay: float = 1.0) -> Any:
    """带重试的获取函数"""
    for i in range(max_retries):
        try:
            result = func()
            if result is not None and not result.empty:
                return result
        except Exception as e:
            print(f"获取失败 (尝试 {i+1}/{max_retries}): {e}")
            time.sleep(delay * (i + 1))  # 指数退避
    return None
```

### 4. 分批处理

```python
def batch_fetch(stock_codes: list, fetch_func, batch_size: int = 100):
    """分批获取数据"""
    results = []
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i + batch_size]
        for code in batch:
            result = fetch_func(code)
            if result is not None:
                results.append(result)
            time.sleep(0.5)  # 间隔控制
    return results
```

---

## 接口限制总结

| 类型 | 限制值 | 建议 |
|------|--------|------|
| 新浪财经 | 5次/秒/IP | 添加0.2秒间隔 |
| 东方财富 | 3次/秒/IP | 添加0.35秒间隔 |
| 单次批量 | ≤100只 | 分批处理 |
| 财务数据 | 无明确限制 | 建议2秒间隔 |

---

## 注意事项

1. **数据延迟**: 免费行情源存在一定延迟（几秒到几十秒），不适合高频交易
2. **用途限制**: 仅供学习研究、复盘分析、策略回测使用
3. **IP风险**: 高频请求可能导致IP被封禁
4. **数据校验**: 重要数据建议交叉验证
5. **更新维护**: 接口可能因数据源变化而调整，请关注 AKShare 更新日志

---

*最后更新: 2026-04-04*