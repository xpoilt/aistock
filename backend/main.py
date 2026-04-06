from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, AsyncIterator
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
                        os.environ[key.strip()] = value.strip()
        print(f"[ENV] Loaded environment variables from {ENV_FILE}")
        print(f"[ENV] OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")

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
    agent_a: int
    agent_b: int
    agent_c: int
    agent_d: int
    agent_e: int
    agent_f: int
    debate_rounds: int = 3
    stock_data: Optional[Dict] = None
    enable_web_search: bool = False

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

async def call_llm_stream(system_prompt: str, user_prompt: str, include_reasoning: bool = False, enable_web_search: bool = False):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured. Please set OPENAI_API_KEY in .env file")
    
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENAI_MODEL", "qwen/qwen3.6-plus:free")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    
    # 添加当前日期时间到 system prompt
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt_with_time = f"{system_prompt}\n\n当前时间：{current_time}"
    
    if enable_web_search:
        system_prompt_with_time += "\n\n【重要提示】用户已开启互联网查询模式，请尽可能基于最新的市场信息和新闻进行分析，确保你的观点和数据是最新的。"
    
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
    print(f"[LLM REQUEST] Enable Web Search: {enable_web_search}")
    print(f"[LLM REQUEST] Current Time: {current_time}")
    print(f"\n[LLM REQUEST] System Prompt:\n{system_prompt_with_time[:500]}{'...' if len(system_prompt_with_time) > 500 else ''}")
    print(f"\n[LLM REQUEST] User Prompt:\n{user_prompt[:500]}{'...' if len(user_prompt) > 500 else ''}")
    print(f"{'='*60}\n")
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", f"{base_url}/chat/completions", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=f"OpenRouter API error: {error_text.decode('utf-8')}")
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
                        except Exception as e:
                            print(f"[WARN] Parse error: {e}")
                            continue
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
    print(f"[DISCUSS] Received request: user_prompt={request.user_prompt[:50] if request.user_prompt else 'None'}...")
    print(f"[DISCUSS] Enable Web Search: {request.enable_web_search}")
    session_id = str(uuid.uuid4())

    print(f"[DISCUSS] 正在获取 agents: A={request.agent_a}, B={request.agent_b}, C={request.agent_c}, D={request.agent_d}, E={request.agent_e}, F={request.agent_f}")
    
    agent_a = get_agent_by_id(request.agent_a)
    agent_b = get_agent_by_id(request.agent_b)
    agent_c = get_agent_by_id(request.agent_c)
    agent_d = get_agent_by_id(request.agent_d)
    agent_e = get_agent_by_id(request.agent_e)
    agent_f = get_agent_by_id(request.agent_f)

    print(f"[DISCUSS] 获取结果: A={agent_a}, B={agent_b}, C={agent_c}, D={agent_d}, E={agent_e}, F={agent_f}")
    
    if not all([agent_a, agent_b, agent_c, agent_d, agent_e, agent_f]):
        raise HTTPException(status_code=400, detail="One or more agents not found")

    stock_info = ""
    
    if request.stock_code:
        stock_info = f"\n\n【股票数据】\n股票代码: {request.stock_code}\n"
        
        if request.stock_data:
            sd = request.stock_data
            if sd.get("daily_data"):
                stock_info += "\n最近交易日数据:\n"
                for d in sd["daily_data"][:5]:
                    stock_info += f"  {d['date']}: 开盘={d['open']}, 收盘={d['close']}, 最高={d['high']}, 最低={d['low']}, 成交量={d['volume']}\n"
            if sd.get("fundamental_data"):
                stock_info += "\n财务数据:\n"
                for f in sd["fundamental_data"][:2]:
                    stock_info += f"  营收={f['revenue']}, 利润={f['profit']}, 净利润={f['net_profit']}\n"
        
        print(f"[DISCUSS] 正在获取 {request.stock_code} 的基本面数据...")
        try:
            fundamental_data = await fetch_stock_fundamental_data(request.stock_code)
            if fundamental_data:
                stock_info += f"\n{fundamental_data}"
        except Exception as e:
            print(f"[WARN] 获取基本面数据失败，继续流程: {e}")

    abc_content = {}

    async def event_generator() -> AsyncIterator[str]:
        nonlocal stock_info
        nonlocal abc_content

        def build_stock_context():
            return f"股票代码: {request.stock_code or '未指定'}{stock_info}\n\n"

        def build_abc_context():
            ctx = ""
            if abc_content.get('A'):
                ctx += f"\n【{agent_a['name']}】的观点:\n{abc_content['A']}\n"
            if abc_content.get('B'):
                ctx += f"\n【{agent_b['name']}】的观点:\n{abc_content['B']}\n"
            if abc_content.get('C'):
                ctx += f"\n【{agent_c['name']}】的观点:\n{abc_content['C']}\n"
            return ctx

        async def call_agent_stream(agent, prompt, agent_label):
            print(f"[AGENT_STREAM] 开始: {agent['name']} ({agent_label})")
            full_content = ""
            yield f"data: {json.dumps({'type': 'thinking_start', 'agent': agent['name'], 'agent_label': agent_label}, ensure_ascii=False)}\n\n"
            async for chunk in call_llm_stream(agent["system_prompt"], prompt, enable_web_search=request.enable_web_search):
                if chunk["type"] == "chunk":
                    full_content += chunk["content"]
                    data = {'type': 'chunk', 'content': chunk["content"], 'agent': agent['name'], 'agent_label': agent_label}
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                else:
                    data = {'type': 'done', 'content': full_content, 'agent': agent['name'], 'agent_label': agent_label}
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        prompt_base = f"请基于以下主题发表你的专业分析:\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}"

        prompt_a = f"{prompt_base}\n\n你是{agent_a['name']}，请给出你的专业分析。"
        prompt_b = f"{prompt_base}\n\n你是{agent_b['name']}，请给出你的专业分析。"
        prompt_c = f"{prompt_base}\n\n你是{agent_c['name']}，请给出你的专业分析。"

        full_content_a = ""
        full_content_b = ""
        full_content_c = ""

        async for chunk_data in call_agent_stream(agent_a, prompt_a, 'A'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        full_content_a = data.get('content', '')
                except:
                    pass

        abc_content['A'] = full_content_a

        async for chunk_data in call_agent_stream(agent_b, prompt_b, 'B'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        full_content_b = data.get('content', '')
                except:
                    pass

        abc_content['B'] = full_content_b

        async for chunk_data in call_agent_stream(agent_c, prompt_c, 'C'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        full_content_c = data.get('content', '')
                except:
                    pass

        abc_content['C'] = full_content_c
        print(f"[DISCUSS] ABC 完成，准备开始 Agent D...")

        prompt_d_init = f"你是{agent_d['name']}。\n\n请基于以下三位分析师的观点，进行综合分析并给出初步的投资建议：\n{build_abc_context()}\n\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}\n\n请综合ABC的意见，给出你的分析和建议（可以同意或反对他们的观点）。"
        d_content = ""
        d_thinking = True
        print(f"[DISCUSS] 开始调用 Agent D...")
        async for chunk_data in call_agent_stream(agent_d, prompt_d_init, 'D'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        d_content = data.get('content', '')
                        d_thinking = False
                except:
                    pass

        prompt_e_comment_d = f"你是{agent_e['name']}。\n\n以下是{agent_d['name']}的综合分析：\n{d_content}\n\n{build_abc_context()}\n\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}\n\n请批判性地分析{agent_d['name']}的观点，指出其中的优点和不足，并给出你的投资建议。"
        e_content = ""
        async for chunk_data in call_agent_stream(agent_e, prompt_e_comment_d, 'E'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        e_content = data.get('content', '')
                except:
                    pass

        prompt_d_comment_e = f"你是{agent_d['name']}。\n\n以下是{agent_e['name']}对你的观点的评论：\n{e_content}\n\n你的原始观点是：\n{d_content}\n\n{build_abc_context()}\n\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}\n\n请回应{agent_e['name']}的评论，维护、修正或改变你的原始立场。"
        async for chunk_data in call_agent_stream(agent_d, prompt_d_comment_e, 'D'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        d_content = data.get('content', '')
                except:
                    pass

        for round_num in range(request.debate_rounds):
            prompt_e_rebuttal = f"你是{agent_e['name']}。\n\n这是第{round_num + 1}轮讨论。\n\n{agent_d['name']}的最新观点：\n{d_content}\n\n{agent_e['name']}之前的评论：\n{e_content}\n\n{build_abc_context()}\n\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}\n\n请继续批判性地回应{agent_d['name']}的观点。"
            e_prev = e_content
            async for chunk_data in call_agent_stream(agent_e, prompt_e_rebuttal, 'E'):
                yield chunk_data
                if chunk_data.startswith("data: "):
                    try:
                        data = json.loads(chunk_data[6:])
                        if data.get('type') == 'done':
                            e_content = data.get('content', '')
                    except:
                        pass

            prompt_d_response = f"你是{agent_d['name']}。\n\n这是第{round_num + 1}轮讨论。\n\n{agent_e['name']}对你的最新回应：\n{e_content}\n\n你之前的观点：\n{d_content}\n\n{build_abc_context()}\n\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}\n\n请回应{agent_e['name']}的评论，维护或修正你的立场。"
            d_prev = d_content
            async for chunk_data in call_agent_stream(agent_d, prompt_d_response, 'D'):
                yield chunk_data
                if chunk_data.startswith("data: "):
                    try:
                        data = json.loads(chunk_data[6:])
                        if data.get('type') == 'done':
                            d_content = data.get('content', '')
                    except:
                        pass

        prompt_f_final = f"你是{agent_f['name']}。\n\n以下是最终讨论总结：\n\n{agent_a['name']}的观点：\n{abc_content.get('A', '')}\n\n{agent_b['name']}的观点：\n{abc_content.get('B', '')}\n\n{agent_c['name']}的观点：\n{abc_content.get('C', '')}\n\n{agent_d['name']}的综合分析与最终立场：\n{d_content}\n\n{agent_e['name']}的批判性评论与最终立场：\n{e_content}\n\n{build_stock_context()}\n\n讨论主题: {request.user_prompt}\n\n请综合所有意见，给出最终的投资决策。你的输出必须包含一个JSON格式的决策结果，格式如下：\n{{\"decision\": \"BUY/HOLD/SELL\", \"confidence\": 0.85, \"summary\": \"决策理由摘要\"}}\n\n请确保输出是合法的JSON格式。"

        final_decision = ""
        async for chunk_data in call_agent_stream(agent_f, prompt_f_final, 'F'):
            yield chunk_data
            if chunk_data.startswith("data: "):
                try:
                    data = json.loads(chunk_data[6:])
                    if data.get('type') == 'done':
                        final_decision = data.get('content', '')
                except:
                    pass

        try:
            json_start = final_decision.find('{')
            json_end = final_decision.rfind('}') + 1
            decision_json = json.loads(final_decision[json_start:json_end]) if json_start != -1 and json_end > json_start else {"decision": "ERROR", "raw": final_decision}
        except:
            decision_json = {"decision": "ERROR", "raw": final_decision}

        yield f"data: {json.dumps({'type': 'final_decision', 'decision': decision_json, 'summary': final_decision}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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

def get_sse_historical_data(stock_code: str, begin_date: str = "20200101", end_date: str = "20500101"):
    import requests
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

def save_sse_data_to_db(cursor, stock_code: str, data):
    if not data or "kline" not in data:
        return 0
    
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
    
    return success_count

async def fetch_and_save_stock_data(stock_code: str):
    import sqlite3
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    init_db()
    
    conn = sqlite3.connect(str(STOCK_DB))
    cursor = conn.cursor()
    
    print(f"[INFO] 正在使用上交所接口获取 {stock_code} 的数据...")
    
    success = False
    for retry in range(3):
        data = get_sse_historical_data(stock_code, "20240101", "20500101")
        
        if data:
            saved_count = save_sse_data_to_db(cursor, stock_code, data)
            if saved_count > 0:
                print(f"[INFO] 上交所接口成功获取 {saved_count} 条记录")
                success = True
                break
            else:
                if retry < 2:
                    print(f"[WARN] 未获取到数据，等待 2 秒后重试 ({retry + 1}/3)...")
                    import time
                    time.sleep(2)
        else:
            if retry < 2:
                print(f"[WARN] 请求失败，等待 2 秒后重试 ({retry + 1}/3)...")
                import time
                time.sleep(2)
    
    if not success:
        print(f"[WARN] 上交所接口获取失败，尝试使用 akshare...")
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20240101", end_date="20500101", adjust="")
            
            if df is not None and len(df) > 0:
                print(f"[INFO] akshare 成功获取 {len(df)} 条记录")
                saved_count = 0
                for _, row in df.iterrows():
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO daily_price (stock_code, trade_date, open, high, low, close, volume, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (stock_code, str(row['日期']), float(row['开盘']), float(row['最高']), float(row['最低']), 
                              float(row['收盘']), float(row['成交量']), float(row['成交额'])))
                        saved_count += 1
                    except Exception as e:
                        pass
                print(f"[INFO] akshare 成功保存 {saved_count} 条记录")
        except Exception as e:
            print(f"[ERROR] akshare 也失败: {e}")
    
    conn.commit()
    conn.close()

async def fetch_stock_fundamental_data(stock_code: str) -> str:
    try:
        import akshare as ak
        print(f"[INFO] 正在获取 {stock_code} 的基本面数据...")
        
        fundamental_info = []
        
        try:
            df_finance = ak.stock_financial_abstract_ths(symbol=stock_code, indicator="按报告期")
            if df_finance is not None and len(df_finance) > 0:
                fundamental_info.append("【财务摘要】")
                for i, row in df_finance.head(3).iterrows():
                    fundamental_info.append(f"  报告期: {row.get('报告期', 'N/A')}")
                    fundamental_info.append(f"  净利润: {row.get('净利润', 'N/A')}")
                    fundamental_info.append(f"  营业收入: {row.get('营业收入', 'N/A')}")
        except Exception as e:
            print(f"[WARN] 获取财务摘要失败: {e}")
        
        try:
            df_valuation = ak.stock_individual_info_em(symbol=stock_code)
            if df_valuation is not None and len(df_valuation) > 0:
                fundamental_info.append("\n【估值信息】")
                for i, row in df_valuation.head(5).iterrows():
                    fundamental_info.append(f"  {row.get('item', '')}: {row.get('value', '')}")
        except Exception as e:
            print(f"[WARN] 获取估值信息失败: {e}")
        
        if len(fundamental_info) > 0:
            result = "\n".join(fundamental_info)
            print(f"[INFO] 成功获取 {stock_code} 的基本面数据")
            return result
        else:
            print(f"[WARN] 未获取到 {stock_code} 的基本面数据")
            return ""
    except Exception as e:
        print(f"[ERROR] 获取基本面数据失败: {e}")
        return ""

@app.post("/api/stock/{stock_code}")
async def fetch_stock_data(stock_code: str):
    try:
        await fetch_and_save_stock_data(stock_code)
        
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
        
        if not daily_data:
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
        
        if not daily_data:
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