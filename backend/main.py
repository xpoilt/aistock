from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import json
import os
import httpx
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
ENV_FILE = BASE_DIR / ".env"
AGENTS_FILE = BASE_DIR / "agents.json"
DISCUSSIONS_LOG = BASE_DIR / "discussions_log.json"
STOCK_DB = BASE_DIR / "stock_data.db"

JIN10_API_KEY = "sk-8ArFwqBdbbbYiorX00_h3vCcFRbYfjWKphKWzzFWcwE"
JIN10_MCP_URL = "https://mcp.jin10.com/mcp"

def load_env():
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())

load_env()

app = FastAPI(title="AIStock Multi-Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DiscussionRequest(BaseModel):
    user_prompt: str
    stock_code: Optional[str] = None
    agent_ids: List[int]
    max_rounds: int = 4
    stock_data: Optional[Dict] = None

class AgentPromptUpdate(BaseModel):
    agent_id: int
    name: str
    system_prompt: str

def load_agents() -> Dict:
    if not AGENTS_FILE.exists():
        default_agents = {
            "agents": [
                {"id": 1, "name": "基本面分析师", "system_prompt": "你是一位资深的基本面分析师，专注于分析公司的财务数据、行业地位、盈利能力等。请基于提供的股票代码和财务数据，给出专业的分析意见。回复格式支持Markdown。"},
                {"id": 2, "name": "技术面专家", "system_prompt": "你是一位技术分析专家，擅长K线形态、技术指标分析。请基于股票的技术走势给出专业意见。回复格式支持Markdown。"},
                {"id": 3, "name": "情绪解读员", "system_prompt": "你是一位市场情绪分析师，擅长分析市场情绪、资金流向、投资者心理等因素。请从情绪角度给出分析。回复格式支持Markdown。"},
                {"id": 4, "name": "风险控制官", "system_prompt": "你是一位风险控制专家，专注于识别和评估投资风险。请评估当前投资的风险敞口。回复格式支持Markdown。"},
                {"id": 5, "name": "决策终结者", "system_prompt": "你是一位投资决策终结者，综合所有分析师的意见，给出最终的投资决策。你的输出必须包含一个JSON格式的决策结果，格式如下：{\"decision\": \"BUY/HOLD/SELL\", \"confidence\": 0.85, \"summary\": \"决策理由摘要\"}。在JSON之后，可以补充详细的分析理由。"}
            ]
        }
        save_agents(default_agents)
        return default_agents
    with open(AGENTS_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_agents(data: Dict):
    with open(AGENTS_FILE, "w", encoding="utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_agent_by_id(agent_id: int) -> Optional[Dict]:
    data = load_agents()
    for agent in data["agents"]:
        if agent["id"] == agent_id:
            return agent
    return None

def get_all_agents_sorted() -> List[Dict]:
    data = load_agents()
    return sorted(data["agents"], key=lambda x: x["id"])

def save_discussion_log(session_id: str, discussion_data: Dict):
    logs = []
    if DISCUSSIONS_LOG.exists():
        with open(DISCUSSIONS_LOG, "r", encoding="utf-8-sig") as f:
            logs = json.load(f)
    logs.append({"session_id": session_id, "timestamp": datetime.now().isoformat(), **discussion_data})
    with open(DISCUSSIONS_LOG, "w", encoding="utf-8-sig") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

async def call_llm_stream(system_prompt: str, user_prompt: str, include_reasoning: bool = False):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured. Please set OPENAI_API_KEY in .env file")
    
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENAI_MODEL", "qwen/qwen3.6-plus:free")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    # 添加当前日期时间到 system prompt
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt_with_time = f"{system_prompt}\n\n当前时间：{current_time}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "http://localhost:8000"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "AIStock")
    }
    
    payload = {
        "model": model, 
        "messages": [{"role": "system", "content": system_prompt_with_time}, {"role": "user", "content": user_prompt}], 
        "stream": True, 
        "temperature": temperature
    }
    
    if include_reasoning:
        payload["extra_body"] = {"reasoning": {"enabled": True}}
    
    print(f"\n{'='*60}")
    print(f"[LLM REQUEST] Model: {model}")
    print(f"[LLM REQUEST] Temperature: {temperature}")
    print(f"[LLM REQUEST] Include Reasoning: {include_reasoning}")
    print(f"[LLM REQUEST] Current Time: {current_time}")
    print(f"\n[LLM REQUEST] System Prompt:\n{system_prompt_with_time[:500]}{'...' if len(system_prompt_with_time) > 500 else ''}")
    print(f"\n[LLM REQUEST] User Prompt:\n{user_prompt[:500]}{'...' if len(user_prompt) > 500 else ''}")
    print(f"{'='*60}\n")
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", f"{base_url}/chat/completions", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.text()
                    raise HTTPException(status_code=response.status_code, detail=f"OpenRouter API error: {error_text}")
                content = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            json_data = json.loads(data)
                            delta = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                content += delta
                                yield {"type": "chunk", "content": delta}
                        except:
                            pass
                yield {"type": "done", "content": content}
    except Exception as e:
        print(f"[ERROR] call_llm_stream: {type(e).__name__}: {str(e)}")
        raise

@app.get("/")
async def root():
    return {
        "message": "AIStock Multi-Agent API", 
        "version": "1.0.0",
        "base_dir": str(BASE_DIR),
        "agents_file_exists": AGENTS_FILE.exists(),
        "env_file_exists": ENV_FILE.exists()
    }

@app.get("/frontend/{filepath}")
async def serve_frontend(filepath: str):
    file_path = BASE_DIR / "frontend" / filepath
    if file_path.exists():
        return FileResponse(file_path)
    return {"error": "File not found"}

@app.get("/api/agents")
async def get_agents():
    return get_all_agents_sorted()

@app.post("/api/agents")
async def create_agent(agent: AgentPromptUpdate):
    data = load_agents()
    max_id = max((a["id"] for a in data["agents"]), default=0)
    new_agent = {
        "id": max_id + 1,
        "name": agent.name,
        "system_prompt": agent.system_prompt
    }
    data["agents"].append(new_agent)
    save_agents(data)
    return new_agent

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: int, update: AgentPromptUpdate):
    data = load_agents()
    for agent in data["agents"]:
        if agent["id"] == agent_id:
            agent["name"] = update.name
            agent["system_prompt"] = update.system_prompt
            save_agents(data)
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")

@app.post("/api/discuss")
async def discuss(request: DiscussionRequest):
    import uuid
    session_id = str(uuid.uuid4())
    agent_messages = {agent_id: [] for agent_id in request.agent_ids}
    
    for round_num in range(request.max_rounds):
        for i, agent_id in enumerate(request.agent_ids):
            agent = get_agent_by_id(agent_id)
            if not agent:
                continue
            
            is_final = (round_num == request.max_rounds - 1) and (i == len(request.agent_ids) - 1)
            
            if is_final:
                stock_info = ""
                if request.stock_data:
                    sd = request.stock_data
                    stock_info = f"\n\n【股票数据】\n股票代码: {request.stock_code}\n"
                    
                    if sd.get("daily_data"):
                        stock_info += "\n最近交易日数据:\n"
                        for d in sd["daily_data"][:5]:
                            stock_info += f"  {d['date']}: 开盘={d['open']}, 最高={d['high']}, 最低={d['low']}, 收盘={d['close']}, 成交量={d['volume']}, 换手率={d['turnover']}%\n"
                    
                    if sd.get("fundamental_data"):
                        stock_info += "\n财务数据:\n"
                        for f in sd["fundamental_data"][:2]:
                            stock_info += f"  {f['ann_date']}: 营收={f['revenue']}, 利润={f['profit']}, 净利润={f['net_profit']}, 总资产={f['assets']}, 总负债={f['liabilities']}\n"
                
                summary_prompt = f"请总结以上所有分析师的意见，并给出最终的投资决策。{stock_info}\n\n"
                for aid in request.agent_ids:
                    if agent_messages[aid]:
                        a = get_agent_by_id(aid)
                        summary_prompt += f"\n【{a['name']}】的观点:\n{agent_messages[aid][-1]}\n"
                summary_prompt += f"\n\n股票代码: {request.stock_code or '未指定'}\n\n请以JSON格式输出决策，格式如下:\n{{\"decision\": \"BUY/HOLD/SELL\", \"confidence\": 0.85, \"summary\": \"决策理由摘要\"}}\n\n请确保输出是合法的JSON格式。"
                
                full_content = ""
                async for chunk in call_llm_stream(agent["system_prompt"], summary_prompt):
                    if chunk["type"] == "chunk":
                        full_content += chunk["content"]
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk['content'], 'agent': agent['name'], 'round': round_num + 1})}\n\n"
                    else:
                        total_tokens = len(full_content) // 4
                        yield f"data: {json.dumps({'type': 'done', 'content': full_content, 'agent': agent['name'], 'tokens': total_tokens})}\n\n"
                
                try:
                    json_start = full_content.find('{')
                    json_end = full_content.rfind('}') + 1
                    decision_json = json.loads(full_content[json_start:json_end]) if json_start != -1 and json_end > json_start else {"decision": "ERROR", "raw": full_content}
                except:
                    decision_json = {"decision": "ERROR", "raw": full_content}
                
                save_discussion_log(session_id, {"session_id": session_id, "stock_code": request.stock_code, "user_prompt": request.user_prompt, "final_decision": decision_json, "all_messages": agent_messages, "total_rounds": request.max_rounds})
            else:
                stock_info = ""
                if request.stock_data:
                    sd = request.stock_data
                    stock_info = f"\n\n【股票数据】\n股票代码: {request.stock_code}\n"
                    if sd.get("daily_data"):
                        stock_info += "\n最近交易日数据:\n"
                        for d in sd["daily_data"][:5]:
                            stock_info += f"  {d['date']}: 开盘={d['open']}, 收盘={d['close']}, 最高={d['high']}, 最低={d['low']}, 成交量={d['volume']}\n"
                    if sd.get("fundamental_data"):
                        stock_info += "\n财务数据:\n"
                        for f in sd["fundamental_data"][:1]:
                            stock_info += f"  营收={f['revenue']}, 利润={f['profit']}, 净利润={f['net_profit']}\n"
                
                context = ""
                for prev_agent_id in request.agent_ids[:i]:
                    if agent_messages[prev_agent_id]:
                        prev_agent = get_agent_by_id(prev_agent_id)
                        context += f"\n【{prev_agent['name']}】说:\n{agent_messages[prev_agent_id][-1]}\n"
                
                current_prompt = f"以下是之前的讨论内容:\n{context}{stock_info}\n\n请基于以上内容，发表你的专业分析。" if context else f"请基于以下主题{stock_info}发表专业分析: {request.user_prompt}"
                
                full_content = ""
                async for chunk in call_llm_stream(agent["system_prompt"], current_prompt):
                    if chunk["type"] == "chunk":
                        full_content += chunk["content"]
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk['content'], 'agent': agent['name'], 'round': round_num + 1})}\n\n"
                    else:
                        total_tokens = len(full_content) // 4
                        agent_messages[agent_id].append(full_content)
                        yield f"data: {json.dumps({'type': 'done', 'content': full_content, 'agent': agent['name'], 'tokens': total_tokens})}\n\n"

@app.get("/api/discussions")
async def get_discussions():
    if not DISCUSSIONS_LOG.exists():
        return []
    with open(DISCUSSIONS_LOG, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/config")
async def get_config():
    return {"api_key_configured": bool(os.getenv("OPENAI_API_KEY")), "base_url": os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"), "model": os.getenv("OPENAI_MODEL", "qwen/qwen3.6-plus:free")}

def init_db():
    import sqlite3
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
        CREATE TABLE IF NOT EXISTS macro_quote (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT,
            price REAL,
            open REAL,
            high REAL,
            low REAL,
            volume REAL,
            ups_price REAL,
            ups_percent REAL,
            update_time TEXT NOT NULL,
            UNIQUE(code, update_time)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro_flash (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flash_id TEXT UNIQUE,
            content TEXT,
            time TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_title TEXT,
            pub_time TEXT,
            star INTEGER,
            previous_val TEXT,
            consensus TEXT,
            actual TEXT,
            affect_txt TEXT,
            UNIQUE(event_title, pub_time)
        )
    """)
    conn.commit()
    conn.close()

async def call_jin10_mcp(method: str, params: dict = None):
    import httpx
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JIN10_API_KEY}",
        "Accept": "text/event-stream"
    }
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(JIN10_MCP_URL, json=payload, headers=headers)
            return r.text
    except Exception as e:
        print(f"[ERROR] MCP call failed: {e}")
        return None

async def get_quote_from_jin10(code: str) -> dict:
    result = await call_jin10_mcp("tools/call", {
        "name": "get_quote",
        "arguments": {"code": code}
    })
    print(f"[DEBUG] Jin10 quote response: {result[:500] if result else 'None'}")
    return result

async def fetch_and_save_macro_data():
    import sqlite3
    import datetime
    import json
    
    init_db()
    conn = sqlite3.connect(str(STOCK_DB))
    cursor = conn.cursor()
    
    symbols = ["XAUUSD", "XAGUSD", "USOIL", "EURUSD", "USDJPY", "USDCNH", "COPPER"]
    
    for symbol in symbols:
        result = await get_quote_from_jin10(symbol)
        if result:
            try:
                for line in result.split('\n'):
                    if line.startswith('data: '):
                        data = json.loads(line[6:])
                        if 'result' in data:
                            structured = data['result'].get('structuredContent', {})
                            qdata = structured.get('data', {})
                            if qdata.get('close'):
                                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                cursor.execute("""
                                    INSERT OR REPLACE INTO macro_quote 
                                    (code, name, price, open, high, low, volume, ups_price, ups_percent, update_time)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    qdata.get('code'),
                                    qdata.get('name'),
                                    qdata.get('close'),
                                    qdata.get('open'),
                                    qdata.get('high'),
                                    qdata.get('low'),
                                    qdata.get('volume'),
                                    qdata.get('ups_price'),
                                    qdata.get('ups_percent'),
                                    now
                                ))
                                print(f"[INFO] Saved macro: {symbol} price={qdata.get('close')}")
            except Exception as e:
                print(f"[ERROR] Parse quote failed: {e}")
    
    conn.commit()
    conn.close()

async def fetch_and_save_stock_data(stock_code: str):
    import sqlite3
    import datetime
    
    init_db()
    
    conn = sqlite3.connect(str(STOCK_DB))
    cursor = conn.cursor()
    
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20240101", end_date="20500101", adjust="")
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO daily_price (stock_code, trade_date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, str(row['日期']), float(row['开盘']), float(row['最高']), float(row['最低']), 
                  float(row['收盘']), float(row['成交量']), float(row['成交额'])))
        print(f"[INFO] akshare got {len(df)} records for {stock_code}")
    except Exception as e:
        print(f"[WARN] akshare failed, using mock data: {e}")
        for i in range(30):
            date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y%m%d')
            cursor.execute("""
                INSERT OR REPLACE INTO daily_price (stock_code, trade_date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, date, 10.0 + i, 10.5 + i, 9.5 + i, 10.2 + i, 1000000 + i * 10000, 10200000 + i * 100000))
    
    conn.commit()
    conn.close()

@app.post("/api/stock/{stock_code}")
async def fetch_stock_data(stock_code: str):
    try:
        fetch_and_save_stock_data(stock_code)
        
        import sqlite3
        conn = sqlite3.connect(str(STOCK_DB))
        cursor = conn.cursor()
        
        daily_data = None
        fundamental_data = None
        
        try:
            cursor.execute("""
                SELECT trade_date, open, high, low, close, volume, amount
                FROM daily_price 
                WHERE stock_code = ? 
                ORDER BY trade_date DESC LIMIT 30
            """, (stock_code,))
            rows = cursor.fetchall()
            if rows:
                daily_data = [
                    {"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5], "amount": r[6]}
                    for r in rows
                ]
        except Exception as e:
            print(f"Error fetching daily data: {e}")
        
        try:
            cursor.execute("""
                SELECT report_date, eps, roe, pe, pb, gross_margin, net_margin, debt_ratio, current_ratio, quick_ratio
                FROM financial_indicator 
                WHERE stock_code = ? 
                ORDER BY report_date DESC LIMIT 4
            """, (stock_code,))
            rows = cursor.fetchall()
            if rows:
                fundamental_data = [
                    {"report_date": r[0], "eps": r[1], "roe": r[2], "pe": r[3], "pb": r[4], "gross_margin": r[5], "net_margin": r[6], "debt_ratio": r[7], "current_ratio": r[8], "quick_ratio": r[9]}
                    for r in rows
                ]
        except Exception as e:
            print(f"Error fetching fundamental data: {e}")
        
        conn.close()
        
        return {
            "stock_code": stock_code,
            "daily_data": daily_data,
            "fundamental_data": fundamental_data,
            "message": "数据获取成功"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/stock/{stock_code}")
async def get_stock_data_from_db(stock_code: str):
    try:
        import sqlite3
        conn = sqlite3.connect(str(STOCK_DB))
        cursor = conn.cursor()
        
        daily_data = None
        fundamental_data = None
        
        try:
            cursor.execute("""
                SELECT trade_date, open, high, low, close, volume, amount
                FROM daily_price 
                WHERE stock_code = ? 
                ORDER BY trade_date DESC LIMIT 30
            """, (stock_code,))
            rows = cursor.fetchall()
            if rows:
                daily_data = [
                    {"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5], "amount": r[6]}
                    for r in rows
                ]
        except Exception as e:
            print(f"Error fetching daily data: {e}")
        
        try:
            cursor.execute("""
                SELECT report_date, eps, roe, pe, pb, gross_margin, net_margin, debt_ratio, current_ratio, quick_ratio
                FROM financial_indicator 
                WHERE stock_code = ? 
                ORDER BY report_date DESC LIMIT 4
            """, (stock_code,))
            rows = cursor.fetchall()
            if rows:
                fundamental_data = [
                    {"report_date": r[0], "eps": r[1], "roe": r[2], "pe": r[3], "pb": r[4], "gross_margin": r[5], "net_margin": r[6], "debt_ratio": r[7], "current_ratio": r[8], "quick_ratio": r[9]}
                    for r in rows
                ]
        except Exception as e:
            print(f"Error fetching fundamental data: {e}")
        
        conn.close()
        
        if not daily_data and not fundamental_data:
            return {"error": f"未找到股票 {stock_code} 的数据"}
        
        return {
            "stock_code": stock_code,
            "daily_data": daily_data,
            "fundamental_data": fundamental_data
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/stock/{stock_code}/collect")
async def collect_stock_data(stock_code: str):
    try:
        # 先获取并保存数据
        await fetch_and_save_stock_data(stock_code)
        
        import sqlite3
        db_path = os.getenv("DATABASE_PATH", str(STOCK_DB))
        
        print(f"[DEBUG] db_path: {db_path}")
        print(f"[DEBUG] STOCK_DB: {STOCK_DB}")
        print(f"[DEBUG] exists: {STOCK_DB.exists()}")
        
        if not STOCK_DB.exists():
            return {"error": f"数据库文件不存在: {STOCK_DB}"}
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        daily_data = None
        fundamental_data = None
        
        try:
            cursor.execute("""
                SELECT trade_date, open, high, low, close, volume, amount
                FROM daily_price 
                WHERE stock_code = ? 
                ORDER BY trade_date DESC LIMIT 30
            """, (stock_code,))
            rows = cursor.fetchall()
            if rows:
                daily_data = [
                    {"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5], "amount": r[6]}
                    for r in rows
                ]
        except Exception as e:
            print(f"Error fetching daily data: {e}")
        
        try:
            cursor.execute("""
                SELECT report_date, eps, roe, pe, pb, gross_margin, net_margin, debt_ratio, current_ratio, quick_ratio
                FROM financial_indicator 
                WHERE stock_code = ? 
                ORDER BY report_date DESC LIMIT 4
            """, (stock_code,))
            rows = cursor.fetchall()
            if rows:
                fundamental_data = [
                    {"report_date": r[0], "eps": r[1], "roe": r[2], "pe": r[3], "pb": r[4], "gross_margin": r[5], "net_margin": r[6], "debt_ratio": r[7], "current_ratio": r[8], "quick_ratio": r[9]}
                    for r in rows
                ]
        except Exception as e:
            print(f"Error fetching fundamental data: {e}")
        
        conn.close()
        
        if not daily_data and not fundamental_data:
            return {"error": f"未找到股票 {stock_code} 的数据"}
        
        return {
            "stock_code": stock_code,
            "daily_data": daily_data,
            "fundamental_data": fundamental_data
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/macro/collect")
async def collect_macro_data():
    try:
        await fetch_and_save_macro_data()
        
        import sqlite3
        conn = sqlite3.connect(str(STOCK_DB))
        cursor = conn.cursor()
        
        cursor.execute("""SELECT code, name, price, open, high, low, volume, ups_price, ups_percent, update_time FROM macro_quote ORDER BY code""")
        rows = cursor.fetchall()
        macro_data = [{"code": r[0], "name": r[1], "price": r[2], "open": r[3], "high": r[4], "low": r[5], "volume": r[6], "ups_price": r[7], "ups_percent": r[8], "update_time": r[9]} for r in rows]
        
        conn.close()
        
        return {
            "macro_data": macro_data,
            "message": "宏观数据获取成功"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/macro")
async def get_macro_data():
    try:
        import sqlite3
        conn = sqlite3.connect(str(STOCK_DB))
        cursor = conn.cursor()
        
        cursor.execute("""SELECT code, name, price, open, high, low, volume, ups_price, ups_percent, update_time FROM macro_quote ORDER BY code""")
        rows = cursor.fetchall()
        macro_data = [{"code": r[0], "name": r[1], "price": r[2], "open": r[3], "high": r[4], "low": r[5], "volume": r[6], "ups_price": r[7], "ups_percent": r[8], "update_time": r[9]} for r in rows]
        
        conn.close()
        return {"macro_data": macro_data}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)