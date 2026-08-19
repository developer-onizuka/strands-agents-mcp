import os

os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["STRANDS_TELEMETRY_ENABLED"] = "false"
os.environ["OPENTELEMETRY_PYTHON_IMPLEMENTATION"] = "python"

import json
import asyncio
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

from strands import Agent, tool
from strands.models import OllamaModel
from strands.tools.mcp import MCPClient
from mcp.client.sse import sse_client


# --- MCP サーバー & LLM の初期化 ---
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://192.168.33.3:5001/sse")

local_model = OllamaModel(
    host="http://svc-ollama:11434",
    model_id="llama3.2:3b",
    options={
        "temperature": 0.0
    }
)

# =============================================================================
# 1. サブエージェントのステータス管理 & ストリーム結合ユーティリティ
# =============================================================================
class SubAgentState:
    def __init__(self):
        self.queue: Optional[asyncio.Queue] = None

_mcp_state = SubAgentState()
_reporter_state = SubAgentState()

async def send_event(queue: Optional[asyncio.Queue], message: str, stage: str, tool_name: Optional[str] = None):
    """サブエージェントの進捗イベントをキューに送信"""
    if not queue:
        return
    progress = {"message": message, "stage": stage}
    if tool_name:
        progress["tool_name"] = tool_name
    await queue.put({"event": {"subAgentProgress": progress}})

async def merge_streams(stream, queue: asyncio.Queue):
    """オーケストレーターとサブエージェントのストリームを統合"""
    create_task = asyncio.create_task
    main = create_task(anext(stream, None))
    sub = create_task(queue.get())
    waiting = {main, sub}
    
    while waiting:
        ready_chunks, waiting = await asyncio.wait(
            waiting, return_when=asyncio.FIRST_COMPLETED
        )
        for ready_chunk in ready_chunks:
            # オーケストレーター（親）のイベント
            if ready_chunk == main:
                event = ready_chunk.result()
                if event is not None:
                    yield event
                    main = create_task(anext(stream, None))
                    waiting.add(main)
                else:
                    main = None
            
            # サブエージェント（子）のイベント
            elif ready_chunk == sub:
                try:
                    sub_event = ready_chunk.result()
                    yield sub_event
                    sub = create_task(queue.get())
                    waiting.add(sub)
                except Exception:
                    sub = None
        
        if main is None and queue.empty():
            break

async def _extract(queue: Optional[asyncio.Queue], agent_name: str, event, state: dict):
    """ストリームイベントからテキストおよびツール使用イベントを抽出しキューへ配分"""
    if isinstance(event, str):
        state["text"] += event
        if queue:
            delta = {"delta": {"text": event}}
            await queue.put({"event": {"contentBlockDelta": delta}})
    elif isinstance(event, dict) and "event" in event:
        event_data = event["event"]
        
        # ツール呼び出しの検出
        if "contentBlockStart" in event_data:
            block = event_data["contentBlockStart"]
            start_data = block.get("start", {})
            if "toolUse" in start_data:
                tool_name = start_data["toolUse"].get("name", "unknown")
                await send_event(queue, f"「{agent_name}」がツール「{tool_name}」を実行中", "tool_use", tool_name)
        
        # テキスト増分（Delta）の検出
        if "contentBlockDelta" in event_data:
            block = event_data["contentBlockDelta"]
            delta = block.get("delta", {})
            if "text" in delta:
                state["text"] += delta["text"]
        
        if queue:
            await queue.put(event)

# =============================================================================
# 2. サブエージェント (Tools) の定義
# =============================================================================
@tool
async def mcp_agent(image_path: str) -> str:
    """Detects face coordinates from an image file path."""
    queue = _mcp_state.queue
    state = {"text": ""}
    await send_event(queue, "顔検出エージェント (mcp_agent) を呼び出しました", "start")
    
    try:
        mcp_client = MCPClient(lambda: sse_client(MCP_SERVER_URL))
        with mcp_client:
            mcp_tools = mcp_client.list_tools_sync()
            agent = Agent(
                model=local_model,
                tools=mcp_tools,
                system_prompt="与えられた画像から顔の座標数値のみを検出して返してください。説明文は不要です。"
            )
            # 非同期ストリーミング呼び出し
            async for event in agent.stream_async(f"Detect face in: {image_path}"):
                await _extract(queue, "mcp_agent", event, state)
                
        await send_event(queue, "顔検出処理が完了しました", "complete")
        return state["text"]
    except Exception as e:
        await send_event(queue, f"顔検出処理に失敗しました: {e}", "error")
        return f"Error in mcp_agent: {e}"

@tool
async def reporter_agent(text: str) -> str:
    """Generates a summary report. Always pass the detection result string into the 'text' argument."""
    queue = _reporter_state.queue
    state = {"text": ""}
    await send_event(queue, "レポート生成エージェント (reporter_agent) を呼び出しました", "start")
    
    try:
        agent = Agent(
            model=local_model,
            system_prompt="You are a technical report writer. Write a simple markdown summary using the provided text input."
        )
        # 非同期ストリーミング呼び出し
        async for event in agent.stream_async(f"Write a short inspection report for these face coordinates: {text}"):
            await _extract(queue, "reporter_agent", event, state)
            
        await send_event(queue, "レポート生成が完了しました", "complete")
        return state["text"]
    except Exception as e:
        await send_event(queue, f"レポート生成に失敗しました: {e}", "error")
        return f"Error in reporter_agent: {e}"

# =============================================================================
# 3. FastAPI & オーケストレーターの設定
# =============================================================================
app = FastAPI(title="Strands Multi-Agent MCP Streaming API")

class PromptRequest(BaseModel):
    prompt: str

ORCHESTRATOR_SYSTEM_PROMPT = """You are a precise task orchestrator.
STRICT INSTRUCTIONS:
Step 1: Call `mcp_agent` with the image file path.
Step 2: Take the output string from `mcp_agent` and pass it directly to `reporter_agent` using parameter 'text'.
Step 3: Return the final text from `reporter_agent`.
"""

orchestrator = Agent(
    model=local_model,
    tools=[mcp_agent, reporter_agent],
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT
)

@app.post("/invocations")
async def invoke(req: PromptRequest):
    # リクエストごとに進捗送信用キューを初期化
    queue = asyncio.Queue()
    _mcp_state.queue = queue
    _reporter_state.queue = queue
    
    async def event_generator():
        try:
            # オーケストレーターのストリームを取得し、サブエージェントのキューと結合
            stream = orchestrator.stream_async(req.prompt)
            async for chunk in merge_streams(stream, queue):
                #data_str = json.dumps(chunk, ensure_ascii=False)
                data_str = json.dumps(chunk, ensure_ascii=False, default=str)
                # SSE (Server-Sent Events) 形式でデータ送信
                yield f"data: {data_str}\n\n"
        finally:
            _mcp_state.queue = None
            _reporter_state.queue = None

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
