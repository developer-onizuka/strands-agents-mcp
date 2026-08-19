import os
from strands import Agent
from strands.models import OllamaModel
from strands.tools.mcp import MCPClient
from mcp.client.sse import sse_client

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://192.168.33.3:5001/sse")

mcp_client = MCPClient(
    lambda: sse_client(MCP_SERVER_URL)
)

local_model = OllamaModel(
    host="http://svc-ollama:11434",
    model_id="llama3.2:3b"
)

SYSTEM_PROMPT = """You are a helpful assistant with access to real tools.
CRITICAL RULES:
1. Call a tool ONLY ONCE per user request. Do NOT call the same tool multiple times.
2. After receiving the tool result, provide the final answer immediately and STOP.
3. Write your final answer ONCE. Never repeat your sentences.
4. Mention the tool name used at the end of your answer.
"""

def agent(prompt_text: str) -> str:
    """Flask等から呼び出されるエージェント実行用エントリーポイント"""
    with mcp_client:
        mcp_tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=local_model,
            tools=mcp_tools,
            system_prompt=SYSTEM_PROMPT
        )
        return str(agent(prompt_text))

if __name__ == "__main__":
    print("--- Running Direct Test ---")
    agent("顔の位置を特定してください。ファイルパスは/strands-agents-mcp/mcp/Bill.jpgです。")
