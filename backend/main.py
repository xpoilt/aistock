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

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
AGENTS_FILE = BASE_DIR / "agents.json"
DISCUSSIONS_LOG = BASE_DIR / "discussions_log.json"

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
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "http://localhost:8000"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "AIStock")
    }
    
    payload = {
        "model": model, 
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
        "stream": True, 
        "temperature": temperature
    }
    
    if include_reasoning:
        payload["extra_body"] = {"reasoning": {"enabled": True}}
    
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
                summary_prompt = "请总结以上所有分析师的意见，并给出最终的投资决策。\n\n"
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
                context = ""
                for prev_agent_id in request.agent_ids[:i]:
                    if agent_messages[prev_agent_id]:
                        prev_agent = get_agent_by_id(prev_agent_id)
                        context += f"\n【{prev_agent['name']}】说:\n{agent_messages[prev_agent_id][-1]}\n"
                
                current_prompt = f"以下是之前的讨论内容:\n{context}\n\n请基于以上内容，发表你的专业分析。股票代码: {request.stock_code or '未指定'}" if context else f"请基于以下主题发表专业分析: {request.user_prompt}\n股票代码: {request.stock_code or '未指定'}"
                
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)