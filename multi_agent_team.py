#!/usr/bin/env python3
import urllib.request
import json
import sys
import threading
import time

# --- 設定値 ---
LOCAL_BRIDGE_URL = "http://localhost:11435/v1/chat/completions"

# 物理モデルの定義 (ag-local-bridgeが提供するエイリアスを使用)
MODEL_MANAGER = "antigravity-gemini-3.1-pro-high"  # マネージャー (高推論)
MODEL_FRONTEND = "antigravity-gemini-3-flash"      # フロントエンド (高速)
MODEL_BACKEND = "antigravity-gemini-3-flash"       # バックエンド (高速)
MODEL_QA = "antigravity-gemini-3.1-pro-high"       # QA (高推論)

# コンソール色出力用のANSIエスケープシーケンス
COLOR_RESET = "\033[0m"
COLOR_MANAGER = "\033[1;34m"   # 太字青
COLOR_FRONT = "\033[1;32m"     # 太字緑
COLOR_BACK = "\033[1;33m"      # 太字黄
COLOR_QA = "\033[1;35m"        # 太字マゼンタ
COLOR_SYSTEM = "\033[1;36m"    # 太字シアン

def print_log(sender, message, color):
    """色付きでタイムラインログを表示する"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {sender}:{COLOR_RESET}")
    # インデントして表示
    for line in message.strip().split('\n'):
        print(f"  {line}")
    print()

def call_bridge(model, system_prompt, user_prompt, temperature=0.7):
    """ag-local-bridgeのOpenAI互換エンドポイントを呼び出す (標準ライブラリのみ使用)"""
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature
    }
    
    req = urllib.request.Request(
        LOCAL_BRIDGE_URL,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['choices'][0]['message']['content']
    except Exception as e:
        return f"エラーが発生しました: {e}\n(Antigravity Local Bridgeが起動していて、ポート11435が有効か確認してください)"

def run_multi_agent_team(user_requirement):
    conversation_logs = []
    
    print_log("SYSTEM", f"6層/4人体制マルチエージェントを起動します。\n接続先: {LOCAL_BRIDGE_URL}\n要求定義:\n{user_requirement}", COLOR_SYSTEM)
    
    # ==========================================
    # 1. マネージャーの初期分析・基本案と代替案の提示
    # ==========================================
    manager_sys = (
        "あなたは開発プロジェクトの統括マネージャーです。ユーザーの要件を分析し、考慮漏れを指摘してください。\n"
        "【重要】ユーザーの要求通りに実装する「基本案」だけでなく、ユーザーが思いつかないような「別角度から課題を解決する代替案（別アプローチ）」を必ず1つ提案してください。\n"
        "その後、フロントエンド、バックエンド、QAの3名に対して、基本案と代替案の両方の視点から議論し、QAが意見を取りまとめるよう指示を出してください。"
    )
    
    manager_prompt = f"ユーザーの要件:\n{user_requirement}"
    
    print(f"{COLOR_SYSTEM}[1/4] マネージャーが要件を分析し、方針を策定中...{COLOR_RESET}")
    manager_instruction = call_bridge(MODEL_MANAGER, manager_sys, manager_prompt)
    print_log("マネージャー (Manager)", manager_instruction, COLOR_MANAGER)
    conversation_logs.append(("Manager (初期指示)", manager_instruction))
    
    # ==========================================
    # 2. エンジニア（フロント ＆ バック）の並行設計
    # ==========================================
    front_sys = (
        "あなたはフロントエンドエンジニアです。マネージャーの指示（基本案・代替案）を確認し、\n"
        "UI/UX設計、画面遷移、フロントエンド実装方針を検討してください。"
    )
    back_sys = (
        "あなたはバックエンドエンジニアです。マネージャーの指示（基本案・代替案）を確認し、\n"
        "データベース設計、API設計、バックエンドおよびロジック実装方針を検討してください。"
    )
    
    front_result = [None]
    back_result = [None]
    
    def run_front():
        print(f"{COLOR_SYSTEM}  - フロントエンドエンジニアが設計中...{COLOR_RESET}")
        front_result[0] = call_bridge(MODEL_FRONTEND, front_sys, manager_instruction)
        
    def run_back():
        print(f"{COLOR_SYSTEM}  - バックエンドエンジニアが設計中...{COLOR_RESET}")
        back_result[0] = call_bridge(MODEL_BACKEND, back_sys, manager_instruction)
        
    # スレッドによる並行処理 (アプローチ④)
    t1 = threading.Thread(target=run_front)
    t2 = threading.Thread(target=run_back)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    print_log("フロントエンド (Front-end)", front_result[0], COLOR_FRONT)
    print_log("バックエンド (Back-end)", back_result[0], COLOR_BACK)
    conversation_logs.append(("Front-end (設計)", front_result[0]))
    conversation_logs.append(("Back-end (設計)", back_result[0]))
    
    # ==========================================
    # 3. QAによる検証・取りまとめ・最終確認
    # ==========================================
    qa_sys = (
        "あなたは品質保証(QA)エンジニアです。フロントエンドとバックエンドの設計案をレビューし、\n"
        "バグ、セキュリティ脆弱性、論理的矛盾、要件漏れがないか検証してください。\n"
        "【重要】報告前に、フロントエンドとバックエンドに対して、追加情報や懸念事項がないか最終確認を促してください。\n"
        "その後、3人の意見を一つに要約・圧縮した最終的な結論レポートを作成し、マネージャーへ報告してください。"
    )
    
    qa_prompt = (
        f"フロントエンド設計案:\n{front_result[0]}\n\n"
        f"バックエンド設計案:\n{back_result[0]}\n\n"
        "エンジニアチーム全体への最終確認（追加情報がないか）も含めて、結論をまとめてマネージャーへ報告してください。"
    )
    
    print(f"{COLOR_SYSTEM}[2/4] QAが設計を検証し、意見を取りまとめ中...{COLOR_RESET}")
    qa_report = call_bridge(MODEL_QA, qa_sys, qa_prompt)
    print_log("QAエンジニア (QA)", qa_report, COLOR_QA)
    conversation_logs.append(("QA (要約・検証報告)", qa_report))
    
    # ==========================================
    # 4. マネージャーの最終レビューと報告
    # ==========================================
    manager_final_sys = (
        "あなたは開発プロジェクトの統括マネージャーです。QAから提出された最終仕様レポートを確認し、\n"
        "考慮漏れや矛盾がないか最終確認してください。\n"
        "問題がなければ、基本案と代替案のメリット・デメリットを整理した上で、最終的な要件定義・設計方針およびコードの構成案をユーザーへ報告してください。"
    )
    
    manager_final_prompt = f"QAからのレポート:\n{qa_report}"
    
    print(f"{COLOR_SYSTEM}[3/4] マネージャーが最終レビューを実行中...{COLOR_RESET}")
    final_output = call_bridge(MODEL_MANAGER, manager_final_sys, manager_final_prompt)
    print_log("マネージャー (最終報告)", final_output, COLOR_MANAGER)
    conversation_logs.append(("Manager (最終報告)", final_output))
    
    # ==========================================
    # 結果の保存とMarkdown出力
    # ==========================================
    print_log("SYSTEM", "マルチエージェントセッションが終了しました。結果を出力します。", COLOR_SYSTEM)
    
    # Markdown形式のレポートを生成
    markdown_report = f"""# 4人体制マルチエージェント 開発設計書

## 👑 マネージャーによる最終結論
{final_output}

---
<details>
<summary>💬 4人体制チームのリアルタイム対話ログを表示</summary>

### 👑 1. マネージャーの初期分析 & 指示
{manager_instruction}

### 🎨 2. フロントエンドの設計方針
{front_result[0]}

### ⚙️ 3. バックエンドの設計方針
{back_result[0]}

### 🔍 4. QAによる検証 & 統合報告
{qa_report}

</details>
"""
    return markdown_report

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # デフォルトのテスト用要求定義
        requirement = (
            "ROS 2とPythonを使用して、Kobukiロボットを安全に追従走行させる制御ノードを作成したい。\n"
            "急な障害物を検知した際は緊急停止し、操舵ホイール（ステアリング）に振動フィードバックを送る仕様にする。"
        )
    else:
        requirement = sys.argv[1]
        
    report = run_multi_agent_team(requirement)
    
    # 結果をMarkdownファイルとして保存
    output_file = "multi_agent_output.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"{COLOR_SYSTEM}最終レポートを '{output_file}' に保存しました。{COLOR_RESET}")
