FROM python:3.11-slim
RUN apt update && apt install -y git
RUN pip3 install httpx fastmcp
RUN git clone https://github.com/developer-onizuka/strands-agents-mcp
ENTRYPOINT ["python3", "/strands-agents-mcp/mcp/app-mcp.py"]
