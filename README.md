

本スクリプトは、Strands Agents SDKを通じてLLMを拡張するMCPクライアントとして機能します。また、同期型のFlaskやStrands環境と非同期前提のMCPサーバーを連携させるため、ツール関数内で局所的にasyncio.run()を使用する設計を採用しています。

MCPのSSE通信は、コネクションを維持したままメッセージをやり取りするステートフルなプロトコルです。これを同期処理で実装すると、データ待機中に実行スレッドがブロックされ、複数アクセス時にFlaskのワーカースレッドが枯渇してシステムがフリーズする危険があります。

そのため、システム全体の同期アーキテクチャは維持しつつ、MCPとの通信部分のみを非同期処理にしてコネクションを適切に管理することで、安定性を損なわない安全な統合を実現しています。


root@strands-agents:/# python3 agent-module3.py 
--- Running Direct Test ---

Tool #1: add_numbers
The answer is 120. I used the Calculator tool.The answer is 120. I used the Calculator tool.


Tool #2: detect_faces
顔の位置は、右上から左下の順に、(270, 444, 563, 150) です。


pip install strands-agents ollama
pip install strands-agents-tools
