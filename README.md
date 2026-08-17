# Strands Agents SDKからMCP Serverを呼び出す。

# 0. 必要なもの
メモリ24GB程度のノートPC 1台<br>

# 1. Goal
ローカルのKubernetes環境に、**Strands Agents SDKとMCP** を活用したAIエージェントシステムを構築すること。

LLM（Ollama）に対して、ローカル関数（簡単な計算等）とMCP経由の外部API（顔認識等）の両方をツールとして提供し、ユーザーからの自然言語の指示に応じてLLMが自律的にツールを使い分ける仕組みを実装します。今回、実装する各機能を以下図に示す。

```
                                    Client PC 
                                +---------------------+
                                | Browser             | #3-12
                                +----------+----------+
                                           |
                                +----------+----------+
                                | LoadBalancer        | #3-7
                                +----------+----------+
                                           |
                                           |
   Enterprise Server (Kubernetes Cluster)  |
+-----------------------+       +----------|----------+              +-------------------------+
| Ollama                |       | Web App  |          |              | MCP Server (SSE)        | #3-8
|  +-----------------+  |       |          V          |              |                         |
|  |     [ LLM ]     |<------------  [Your Prompt]    |  mcp-remote  |  +-------------------+  |
|  |    (Llama3.2)   |          |  +---------------+  |  (JSON/SSE)  |  | svc-mcp           |  |
|  |                 |------------>|  MCP Client   |--+------------->|  | (LoadBalancer IP) |  |
|  +-----------------+  |       |  +---------------+  |              |  +---------+---------+  |
+-----------------------+       +---------------------+              |            |            |                Enterprise Storage
                 #3-10                          #3-11                |  +---------v---------+  |   Data Req    +------------------+
                                                                     |  | Pod: mcp-server   |----------------->|  Object Storage  |
                                                                     |  | (app-mcp.py)      |<-----------------|                  |
                                                                     |  +---------+---------+  |   Data Read   +------------------+
                                                                     |            |            |
                                                                     +------------|------------+
                                                                                  |   Data Put
                                                                                  |
                                                                        SaaS API  |
                                                                     +------------|------------+        
                                                                     |  +---------v---------+  | #3-9
                                                                     |  | faceRecognizerAPI |  |
                                                                     |  +-------------------+  |
                                                                     +-------------------------+
```

# 2. 各ノードのスペック
| Node名 | CPU | Memory | IP Address |
|---|---|---|---|
| master | 4 | 8GB | 192.168.33.100 |
| worker1 | 4 | 8GB | 192.168.33.101 |

# 3. 手順
### 3-1. Hypervisorのインストール
>https://www.oracle.com/jp/virtualization/technologies/vm/downloads/virtualbox-downloads.html

### 3-2. Vagrantのインストール
>https://developer.hashicorp.com/vagrant/install

### 3-3. gitのインストール & git clone
>https://git-scm.com/downloads
```
git clone https://github.com/developer-onizuka/faceRecognizerAPI-mcp
cd faceRecognizerAPI-mcp
```

### 3-4. Master node / Worker nodeを起動する
```
cd kubernetes
vagrant up
cd ..
```

### 3-5. Master nodeへのログイン & git clone
```
cd kubernetes
vagrant ssh master
git clone https://github.com/developer-onizuka/faceRecognizerAPI-mcp
cd faceRecognizerAPI-mcp
```

### 3-6. Kubernetesクラスタの確認
```
kubectl get nodes -A -o wide
kubectl get pods -A -o wide
```
```
$ kubectl get nodes -A -o wide
NAME      STATUS   ROLES           AGE   VERSION   INTERNAL-IP      EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION     CONTAINER-RUNTIME
master    Ready    control-plane   67m   v1.33.3   192.168.33.100   <none>        Ubuntu 24.04.2 LTS   6.8.0-53-generic   containerd://1.7.27
worker1   Ready    node            67m   v1.33.3   192.168.33.101   <none>        Ubuntu 24.04.2 LTS   6.8.0-53-generic   containerd://1.7.27
```
```
$ kubectl get pods -A -o wide
NAMESPACE        NAME                                       READY   STATUS    RESTARTS   AGE   IP               NODE      NOMINATED NODE   READINESS GATES
kube-system      calico-kube-controllers-7498b9bb4c-lngsr   1/1     Running   0          67m   10.10.219.66     master    <none>           <none>
kube-system      calico-node-4wbbs                          1/1     Running   0          67m   192.168.33.101   worker1   <none>           <none>
kube-system      calico-node-8bt9k                          1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
kube-system      coredns-674b8bbfcf-5strr                   1/1     Running   0          67m   10.10.219.67     master    <none>           <none>
kube-system      coredns-674b8bbfcf-kqn54                   1/1     Running   0          67m   10.10.219.65     master    <none>           <none>
kube-system      csi-nfs-controller-8fdc6755d-78qxc         5/5     Running   0          46m   192.168.33.101   worker1   <none>           <none>
kube-system      csi-nfs-node-kjqnr                         3/3     Running   0          46m   192.168.33.100   master    <none>           <none>
kube-system      csi-nfs-node-x2g8q                         3/3     Running   0          46m   192.168.33.101   worker1   <none>           <none>
kube-system      etcd-master                                1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
kube-system      kube-apiserver-master                      1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
kube-system      kube-controller-manager-master             1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
kube-system      kube-proxy-2xdcj                           1/1     Running   0          67m   192.168.33.101   worker1   <none>           <none>
kube-system      kube-proxy-slq7w                           1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
kube-system      kube-scheduler-master                      1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
metallb-system   controller-58fdf44d87-66bfg                1/1     Running   0          67m   10.10.235.129    worker1   <none>           <none>
metallb-system   speaker-ldcz4                              1/1     Running   0          67m   192.168.33.100   master    <none>           <none>
metallb-system   speaker-v8vn6                              1/1     Running   0          67m   192.168.33.101   worker1   <none>           <none>
```
### 3-7. ロードバランサーの設定
ロードバランサーに割り当てるIPアドレスの範囲を指定します。
```
kubectl apply -f metallb-ipaddress.yaml
```

### 3-8. MCP Serverを起動
```
kubectl apply -f app-mcp.yaml
```
本Podは、Strands Agents SDKを通じてLLMを拡張するMCPクライアントとして機能します。また、同期型のFlaskやStrands環境と非同期前提のMCPサーバーを連携させるため、ツール関数内で局所的にasyncio.run()を使用しています。

MCPのSSE通信は、コネクションを維持したままメッセージをやり取りするステートフルなプロトコルです。これを同期処理で実装すると、データ待機中に実行スレッドがブロックされ、複数アクセス時にFlaskのワーカースレッドが枯渇してシステムがフリーズする危険があるため、システム全体の同期アーキテクチャは維持しつつ、MCPとの通信部分のみを非同期処理にしています。

### 3-9. faceRecognizerAPIを起動
```
kubectl apply -f faceRecognizerAPI.yaml
kubectl exec -it pods/face-recognizer-api-xxxxxxxxxx-xxxxx -- /bin/bash
git clone https://github.com/developer-onizuka/faceRecognizerAPI
apt update && apt install -y cmake build-essential git
pip install face_recognition flask opencv-python-headless
cd faceRecognizerAPI/
python3 faceRecognizerAPI.py 
```

### 3-10. ollamaを起動
```
kubectl apply -f ollama.yaml
kubectl exec -it pods/ollama-xxxxxxxxxx-xxxxx -- ollama pull llama3.2:3b
```

### 3-11. FlaskによるWebアプリを起動
```
kubectl apply -f flask-mcp.yaml
```

### 3-12. プロンプトの入力
以下コマンドで、svc-flask-mcpのEXTERNAL-IPを調べて、PC上のブラウザからアクセスします。以下の例では、192.168.33.4:8000にアクセスすることになります。
```
$ kubectl get svc
NAME                      TYPE           CLUSTER-IP       EXTERNAL-IP    PORT(S)          AGE
face-recognizer-api-svc   LoadBalancer   10.99.114.218    192.168.33.2   5000:30672/TCP   97m
kubernetes                ClusterIP      10.96.0.1        <none>         443/TCP          108m
svc-flask-mcp             LoadBalancer   10.106.131.177   192.168.33.4   8000:31939/TCP   91m
svc-mcp                   LoadBalancer   10.100.90.226    192.168.33.3   5001:31947/TCP   91m
svc-ollama                ClusterIP      10.106.254.70    <none>         11434/TCP        101m
```

次に以下のプロンプトを画面のテキストボックスにコピペしてPOSTボタンを押します。
```
顔の位置を特定してください。ファイルパスは/strands-agents-mcp/mcp/Bill.jpgです。
```
プロンプト入力後、以下のように顔の座標が表示されれば成功です。<br><br>
<img src="https://github.com/developer-onizuka/strands-agents-mcp/blob/main/flask.png" width="720">

# 4. まとめ
Enterprise環境（Kubernetes等）におけるローカルLLM（Ollama）およびMCPを活用し、Strands AgentをWebサーバー（Flask）としてカプセル化したAIエージェント環境を構築してみました。

### 4-1. アーキテクチャの特徴とコアコンポーネント
#### Strands Agent (Flask Web Server)
役割: ユーザーインターフェース（Web UI）およびエージェントオーケストレーター<br>
機能: ブラウザからのプロンプト入力の受付、推論実行（Ollama呼び出し）、ツール実行判定（MCP Client機能）、レスポンスの統合制御を担当。

#### LLM Engine (Ollama on Enterprise Server)
役割: プライベート環境での推論処理<br>
機能: 外部クラウド（Anthropic Cloud等）を介さず、オンプレミス／Kubernetes上で安全にオープンモデル推論を実行。

#### MCP Server & External Services
役割: データ・ツールの統合基盤<br>
機能: MCP (Model Context Protocol) 準拠のインターフェース（app-mcp.py）を提供し、Enterprise Storage（Object Storage）のデータ読み書きや外部SaaS API（顔認識API等）との連携を安全に仲介。


### 4-2. 今後の課題
長時間の推論やツール実行におけるレスポンス遅延・ブロッキングの回避やSSEストリーミングへの移行によるUX向上、JWT等を用いたユーザー権限のMCP Serverへの伝播によるエンドツーエンドのアクセス制御、OpenTelemetry等のトレーシング機能を追加したいと思っています。
