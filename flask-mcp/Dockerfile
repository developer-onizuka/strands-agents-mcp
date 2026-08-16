FROM python:3.11-slim
RUN apt update && apt install -y git
RUN pip3 install flask strands-agents ollama strands-agents-tools
RUN git clone https://github.com/developer-onizuka/strands-agents-mcp
ENTRYPOINT ["python3", "/strands-agents-mcp/app3.py"]
