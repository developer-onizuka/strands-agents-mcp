import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP(name="Face Recognizer MCP")

FACE_RECOGNIZER_URL = os.environ.get("FACE_RECOGNIZER_URL", "http://localhost:5000/facerecognizer")

@mcp.tool()
def detect_faces(image_path: str) -> str:
    """It accepts the path to an image file, calls an external face recognition API, and returns the face's coordinate positions (top, right, bottom, left)."""
    try:
        with open(image_path, "rb") as f:
            files = {"img": (image_path, f, "image/jpeg")}
            response = httpx.post(FACE_RECOGNIZER_URL, files=files, timeout=30.0)
            response.raise_for_status()
            return response.text
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=5001)
