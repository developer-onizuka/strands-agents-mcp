import os
from strands import Agent, tool
from strands.models import OllamaModel
from strands.tools.mcp import MCPClient
from mcp.client.sse import sse_client

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://192.168.33.3:5001/sse")

mcp_client = MCPClient(
    lambda: sse_client(MCP_SERVER_URL)
)

local_model = OllamaModel(
    host="http://svc-ollama:11434",
    model_id="llama3.2:3b",
    options={
        "temperature": 0.0
    }
)

@tool
def mcp_agent(image_path: str) -> str:
    """Detects face coordinates from an image file path."""
    #print("\n[DEBUG] >>> 1. mcp_agent is called. <<<")
    with mcp_client:
        mcp_tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=local_model,
            tools=mcp_tools,
            system_prompt="与えられた画像から顔の座標数値のみを検出して返してください。説明文は不要です。"
        )
        result = agent(f"Detect face in: {image_path}")
        #print(f"[DEBUG] mcp_agent returned: {result}")
        return str(result)

@tool
def reporter_agent(text: str) -> str:
    """Generates a summary report. Always pass the detection result string into the 'text' argument."""
    #print("\n[DEBUG] >>> 2. reporter_agent is called. <<<")
    agent = Agent(
        model=local_model,
        system_prompt="You are a technical report writer. Write a simple markdown summary using the provided text input."
    )
    result = agent(f"Write a short inspection report for these face coordinates: {text}")
    return str(result)

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

if __name__ == "__main__":
    print("--- Running Multi-Agent Test ---")
    res = orchestrator("/strands-agents-mcp/mcp/Bill.jpg")
    print("\n================ FINAL OUTPUT ================")
    print(res)
