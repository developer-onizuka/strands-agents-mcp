import os
import asyncio
from strands import Agent, tool
from strands.models import OllamaModel
from mcp import ClientSession
from mcp.client.sse import sse_client

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://192.168.33.3:5001/sse")

@tool
def detect_faces(image_path: str) -> str:
    """Accepts an image file path, calls the remote FastMCP server via SSE, and returns face coordinate positions."""
    
    async def _call_mcp():
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("detect_faces", arguments={"image_path": image_path})
                return result.content[0].text

    try:
        return asyncio.run(_call_mcp())
    except Exception as e:
        return f"MCP Server Connection Error: {str(e)}"

@tool
def add_numbers(a: int, b: int) -> int:
    """Adds two integers together. Call this whenever a sum or addition is required."""
    return a + b

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

agent = Agent(
    model=local_model,
    tools=[add_numbers, detect_faces],
    system_prompt=SYSTEM_PROMPT
)

if __name__ == "__main__":
    print("--- Running Direct Test ---")
    print(agent("What is 50 plus 70? Please also tell me which tool you used."))
    print(agent("顔の位置を特定してください。ファイルパスは/faceRecognizerAPI-mcp/Bill.jpgです。"))

