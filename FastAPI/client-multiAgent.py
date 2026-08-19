import os
import json
import requests
from dotenv import load_dotenv
import streamlit as st

# .envファイルから環境変数をロード
load_dotenv(override=True)

# APIサーバーのURL
API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000/invocations")

# =============================================================================
# ストリーミング UI 制御ロジック
# =============================================================================

def create_state():
    """新しい描画状態を作成"""
    return {
        "containers": [],
        "current_status": None,
        "current_text": None,
        "final_response": ""
    }

def think(container, state):
    """初期の思考中ステータスを表示"""
    with container:
        thinking_status = st.empty()
        thinking_status.status("思考中...", state="running")
    state["containers"].append((thinking_status, "思考中..."))

def change_status(event, container, state):
    """サブエージェントの進捗ステータスを更新"""
    progress_info = event["subAgentProgress"]
    message = progress_info.get("message", "処理中...")
    stage = progress_info.get("stage", "processing")
    
    # 前のステータスを完了状態に更新
    if state["current_status"]:
        status, old_message = state["current_status"]
        status.status(old_message, state="complete")
    
    # 新しいステータスボックスを表示
    with container:
        new_status_box = st.empty()
        display_state = "complete" if stage == "complete" else "running"
        new_status_box.status(message, state=display_state)
    
    status_info = (new_status_box, message)
    state["containers"].append(status_info)
    state["current_status"] = status_info
    state["current_text"] = None

def stream_text(event, container, state):
    """テキストをストリーミング描画"""
    delta = event.get("contentBlockDelta", {}).get("delta", {})
    if "text" not in delta:
        return
    
    # テキスト出力が始まったら進行中のステータスを完了状態にする
    if state["current_text"] is None:
        if state["containers"]:
            status, first_message = state["containers"][0]
            if "思考中" in first_message:
                status.status(first_message, state="complete")
        if state["current_status"]:
            status, message = state["current_status"]
            status.status(message, state="complete")
    
    # テキスト結合とレンダリング
    text = delta["text"]
    state["final_response"] += text
    
    if state["current_text"] is None:
        with container:
            state["current_text"] = st.empty()
            
    if state["current_text"]:
        state["current_text"].markdown(state["final_response"] + "▌")

def finish(state):
    """ストリーム終了時のクリーンアップ処理"""
    # 最終テキスト描画（カーソル文字「▌」をクリア）
    if state["current_text"]:
        state["current_text"].markdown(state["final_response"])
        
    # 残っているステータスボックスをすべて完了状態にする
    for status, message in state["containers"]:
        status.status(message, state="complete")

def extract_stream(data, container, state):
    """SSEイベントデータの振り分け"""
    if not isinstance(data, dict):
        return

    event = data.get("event", {})    
    if "subAgentProgress" in event:
        change_status(event, container, state)
    elif "contentBlockDelta" in event:
        stream_text(event, container, state)
    elif "error" in data:
        error_msg = data.get("error", "Unknown error")
        st.error(f"Agentエラー: {error_msg}")
        state["final_response"] = f"エラー: {error_msg}"

def invoke_agent_stream(prompt, container):
    """FastAPI サーバーから SSE ストリームを受信して描画を行う関数"""
    state = create_state()
    think(container, state)
    
    try:
        # FastAPI サーバーへ POST リクエストを送信 (stream=True で接続を維持)
        response = requests.post(
            API_URL,
            headers={"Content-Type": "application/json"},
            json={"prompt": prompt},
            stream=True,
            timeout=180
        )
        response.raise_for_status()

        # SSE (Server-Sent Events) の1行ずつ処理
        for line in response.iter_lines():
            if not line:
                continue
            
            decoded_line = line.decode("utf-8")
            if decoded_line.startswith("data: "):
                raw_json = decoded_line[6:]  # "data: " のプレフィックスをカット
                try:
                    data = json.loads(raw_json)
                    extract_stream(data, container, state)
                except json.JSONDecodeError:
                    continue

        finish(state)
        return state["final_response"]

    except requests.exceptions.Timeout:
        st.error("処理がタイムアウトしました。応答に時間がかかっています。")
        return ""
    except requests.exceptions.ConnectionError:
        st.error("FastAPI サーバーに接続できませんでした。サーバーが起動しているか確認してください。")
        return ""
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        return ""

# =============================================================================
# メイン画面 UI
# =============================================================================

st.title("Strands Multi-Agent")
st.write("/strands-agents-mcp/mcp/Bill.jpg")

# チャット履歴の初期化
if 'messages' not in st.session_state:
    st.session_state.messages = []

# チャット履歴の描画
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザー入力
if prompt := st.chat_input("メッセージを入力してください。"):
    # ユーザー入力の表示 & 履歴追加
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # エージェントのストリーミング応答表示
    with st.chat_message("assistant"):
        container = st.container()
        final_answer = invoke_agent_stream(prompt, container)
        
        if final_answer:
            st.session_state.messages.append({"role": "assistant", "content": final_answer})
