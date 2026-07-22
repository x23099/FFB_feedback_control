#!/usr/bin/env python3
import urllib.request
import json
import sys
import time
import os

# --- 設定値 ---
LOCAL_BRIDGE_URL = "http://localhost:11435/v1/chat/completions"

# 物理モデルの定義 (実際に選択画面に存在する正式なモデルID)
MODEL_MANAGER = "antigravity-gemini-3.1-pro-high"         # マネージャー (実在する最高性能 Gemini Pro)
MODEL_FRONTEND = "antigravity-gemini-3-flash"              # フロントエンド (実在する Gemini Flash)
MODEL_BACKEND = "antigravity-gemini-3.1-pro-high"         # バックエンド (実在する最高性能 Gemini Pro)
MODEL_QA = "antigravity-claude-opus-4-6-thinking"         # QA (実在する最強検証モデル Claude Opus Thinking)

# コンソール色出力用のANSIエスケープシーケンス
COLOR_RESET = "\033[0m"
COLOR_MANAGER = "\033[1;34m"   # 太字青
COLOR_FRONT = "\033[1;32m"     # 太字緑
COLOR_BACK = "\033[1;33m"      # 太字黄
COLOR_QA = "\033[1;35m"        # 太字マゼンタ
COLOR_SYSTEM = "\033[1;36m"    # 太字シアン
COLOR_USER = "\033[1;37m"      # 太字白

# --- ログディレクトリの設定 ---
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def reset_logs():
    """ログファイルをリセット・初期化する"""
    for agent in ["manager", "frontend", "backend", "qa", "system"]:
        filepath = os.path.join(LOG_DIR, f"{agent}.log")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"=== {agent.upper()} AGENT LOG ===\n\n")

def write_agent_log(agent_key, sender, message):
    """指定されたエージェントのログファイルへ追記出力する"""
    filepath = os.path.join(LOG_DIR, f"{agent_key}.log")
    timestamp = time.strftime("%H:%M:%S")
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {sender}:\n")
        for line in message.strip().split('\n'):
            f.write(f"  {line}\n")
        f.write("\n" + "-"*50 + "\n\n")
        f.flush()

def print_log(sender, message, color, agent_key="system"):
    """色付きでコンソール表示し、同時に該当ログファイルへ記録する"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {sender}:{COLOR_RESET}")
    for line in message.strip().split('\n'):
        print(f"  {line}")
    print()
    write_agent_log(agent_key, sender, message)

def call_bridge_messages(model, messages, temperature=0.7, retries=3):
    """ag-local-bridgeのエンドポイントに会話履歴(messages)配列を送信する"""
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    
    for attempt in range(retries):
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
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait_time = (attempt + 1) * 3
                time.sleep(wait_time)
                continue
            return f"HTTPエラーが発生しました: {e.code} - {e.reason}"
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return f"エラーが発生しました: {e}\n(Antigravity Local Bridgeが起動していて、ポート11435が有効か確認してください)"

def call_bridge(model, system_prompt, user_prompt, temperature=0.7, retries=3):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    return call_bridge_messages(model, messages, temperature, retries)

def parse_manager_response(response_text):
    """マネージャーの返答からJSON部分を抽出してパースする"""
    try:
        cleaned = response_text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        return json.loads(cleaned)
    except Exception:
        return {
            "is_plan_complete": False,
            "summary": "会話から要件を整理中...",
            "question": response_text,
            "options": [
                "1. 上記の提案内容で進める",
                "2. 別の代替案を提示してほしい"
            ],
            "final_plan": ""
        }

def manager_user_discussion_phase(initial_requirement):
    """フェーズ1: マネージャーとユーザーの対話型計画策定"""
    print_log("SYSTEM", f"【フェーズ1】マネージャーとの対話を開始します。\n初期要求:\n{initial_requirement}", COLOR_SYSTEM, "system")
    
    system_prompt = (
        "あなたは開発プロジェクトの統括マネージャーです。ユーザーから提出された要件をもとに、ユーザーと対話して高精度な開発計画書を作成します。\n\n"
        "【対話のルール】\n"
        "1. 計画を確定させるために必要な不明点・仕様の決定事項について、1回につき1〜2つの明確な質問を行ってください。\n"
        "2. 質問には必ずいくつかの選択肢（例: 1, 2, 3...）を添えてください。選択肢以外にもユーザーが自由に文章入力（Other）できるよう考慮した質問にしてください。\n"
        "3. ユーザーと十分に議論が交わされ、計画が完全に完成したと判断した場合のみ `is_plan_complete: true` にし、`final_plan` に詳細な開発計画書を記述してください。\n"
        "4. 必ず以下の純粋なJSONフォーマットのみを出力してください。\n\n"
        "【出力JSONフォーマット】\n"
        "{\n"
        '  "is_plan_complete": false,\n'
        '  "summary": "これまでの決定事項・要件の要約",\n'
        '  "question": "ユーザーへの質問本文",\n'
        '  "options": [\n'
        '    "1. 選択肢Aの説明",\n'
        '    "2. 選択肢Bの説明"\n'
        "  ],\n"
        '  "final_plan": "" // is_plan_completeが true の場合のみ、完成した詳細開発計画書をここに記入\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"初期要件:\n{initial_requirement}"}
    ]

    while True:
        raw_res = call_bridge_messages(MODEL_MANAGER, messages)
        data = parse_manager_response(raw_res)

        # 計画完了の判定
        if data.get("is_plan_complete", False):
            final_plan = data.get("final_plan", raw_res)
            print_log("SYSTEM", "==================== 高精度開発計画書 (案) ====================", COLOR_SYSTEM, "system")
            print(f"{COLOR_MANAGER}{final_plan}{COLOR_RESET}\n")
            write_agent_log("manager", "Manager (高精度開発計画書)", final_plan)
            print_log("SYSTEM", "==================================================================", COLOR_SYSTEM, "system")
            
            # ユーザーへの承認確認
            print_log("マネージャー", "上記の内容で開発計画書を作成いたしました。エンジニアチームへ引き継いで実装を開始してよろしいでしょうか？", COLOR_MANAGER, "manager")
            print(f"{COLOR_SYSTEM}[y / yes]: 承認して実装を開始する{COLOR_RESET}")
            print(f"{COLOR_SYSTEM}[修正内容を入力]: 計画書を再調整・修正する{COLOR_RESET}\n")
            
            try:
                confirm = input(f"{COLOR_USER}承認確認 (y / 修正指示) > {COLOR_RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                confirm = "y"

            if confirm.lower() in ["y", "yes", "ok", "承認", ""]:
                print_log("SYSTEM", "✅ ユーザーの承認を得ました。エンジニアチームへ引き継ぎます。", COLOR_SYSTEM, "system")
                return final_plan
            else:
                print_log("SYSTEM", "🔄 修正指示を受け付けました。マネージャーが計画を再調整します。", COLOR_SYSTEM, "system")
                messages.append({"role": "assistant", "content": raw_res})
                messages.append({"role": "user", "content": f"計画書の修正指示: {confirm}"})
                continue

        # マネージャーからの質問表示
        summary = data.get("summary", "")
        question = data.get("question", "")
        options = data.get("options", [])

        if summary:
            print_log("マネージャー (要約)", summary, COLOR_MANAGER, "manager")
        
        msg_content = question
        if options:
            msg_content += "\n\n【選択肢】\n" + "\n".join(options) + "\n※ 番号を選択するか、自由に入力(Other)してください。"
        
        print_log("マネージャー (質問)", msg_content, COLOR_MANAGER, "manager")

        # ユーザー回答受付
        try:
            user_input = input(f"{COLOR_USER}あなた (回答を入力) > {COLOR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "1"

        if not user_input:
            user_input = "1 (デフォルト選択)"

        messages.append({"role": "assistant", "content": raw_res})
        messages.append({"role": "user", "content": f"ユーザーの回答: {user_input}"})


def engineering_and_qa_phase(final_plan):
    """フェーズ2: エンジニアによるコード設計・製作およびQAデバッグ・検証"""
    print_log("SYSTEM", "【フェーズ2】確定した計画書をもとにエンジニアとQAチームが実装・検証を開始します。", COLOR_SYSTEM, "system")
    conversation_logs = []

    # 1. フロントエンド実装設計
    front_sys = (
        "あなたはフロントエンドエンジニアです。確定した開発計画書をもとに、\n"
        "UI/UX構造、コンポーネント構成、フロントエンドの具体的な実装コード（Python/HTML/JS等）およびコード解説を作成してください。"
    )
    print(f"{COLOR_SYSTEM}  - [1/3] フロントエンドエンジニアがコード・設計を作成中...{COLOR_RESET}")
    front_output = call_bridge(MODEL_FRONTEND, front_sys, f"確定計画書:\n{final_plan}")
    print_log("フロントエンド (Front-end)", front_output, COLOR_FRONT, "frontend")
    conversation_logs.append(("Front-end (コード・設計)", front_output))

    # 2. バックエンド実装設計
    back_sys = (
        "あなたはバックエンドエンジニアです。確定した開発計画書をもとに、\n"
        "システムロジック、データ構造、API、バックエンドの具体的な実装コード（Python等）およびコード解説を作成してください。"
    )
    print(f"{COLOR_SYSTEM}  - [2/3] バックエンドエンジニアがコード・設計を作成中...{COLOR_RESET}")
    back_output = call_bridge(MODEL_BACKEND, back_sys, f"確定計画書:\n{final_plan}")
    print_log("バックエンド (Back-end)", back_output, COLOR_BACK, "backend")
    conversation_logs.append(("Back-end (コード・設計)", back_output))

    # 3. QAデバッグ・セキュリティ検証
    qa_sys = (
        "あなたは品質保証(QA)およびデバッグ専門エンジニアです。\n"
        "フロントエンドとバックエンドのコード・設計案を深くレビューし、\n"
        "1. バグやエッジケースでの不具合\n"
        "2. セキュリティ上の脆弱性\n"
        "3. ２つのコード間の接続・ロジックの不整合\n"
        "を検証し、具体的な修正コード・デバッグアドバイスを含めた検証報告書を作成してください。"
    )
    qa_prompt = (
        f"確定開発計画書:\n{final_plan}\n\n"
        f"フロントエンド実装:\n{front_output}\n\n"
        f"バックエンド実装:\n{back_output}"
    )
    print(f"{COLOR_SYSTEM}  - [3/3] QAエンジニアがコードを検証・デバッグ中...{COLOR_RESET}")
    qa_report = call_bridge(MODEL_QA, qa_sys, qa_prompt)
    print_log("QAエンジニア (QA)", qa_report, COLOR_QA, "qa")
    conversation_logs.append(("QA (デバッグ・検証報告)", qa_report))

    # 4. マネージャーによる最終統括
    manager_sys = (
        "あなたは統括マネージャーです。エンジニアのコードとQAの検証結果を確認し、\n"
        "最終的な納品用レポートとして全体の成果物（確定仕様、完成コード、QA検証結果、今後の運用方針）をきれいにまとめてください。"
    )
    manager_prompt = f"計画書:\n{final_plan}\n\nQA統合レポート:\n{qa_report}"
    print(f"{COLOR_SYSTEM}マネージャーが最終納品レポートを作成中...{COLOR_RESET}")
    final_output = call_bridge(MODEL_MANAGER, manager_sys, manager_prompt)
    print_log("マネージャー (最終総括)", final_output, COLOR_MANAGER, "manager")

    # 成果物の書き出し
    report_md = f"""# インタラクティブ開発マルチエージェント 成果物レポート

## 👑 確定開発計画書 (マネージャー & ユーザー合意)
{final_plan}

---

## 🎨 フロントエンド実装・設計
{front_output}

---

## ⚙️ バックエンド実装・設計
{back_output}

---

## 🔍 QA検証・デバッグレポート
{qa_report}

---

## 🏆 最終総括
{final_output}
"""
    return report_md

def run_multi_agent_team(initial_requirement):
    # フェーズ1: 対話による計画策定（承認確認付き）
    final_plan = manager_user_discussion_phase(initial_requirement)
    
    # フェーズ2: コード制作 & QA検証
    report_md = engineering_and_qa_phase(final_plan)
    
    output_file = "multi_agent_output.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_md)
    print_log("SYSTEM", f"一連の処理が完了しました。成果物レポートを `{output_file}` に保存しました。", COLOR_SYSTEM, "system")
    return report_md

if __name__ == "__main__":
    reset_logs()
    print_log("SYSTEM", "マルチエージェント開発システムを開始します。（終了するには 'exit' または 'quit' と入力）", COLOR_SYSTEM, "system")
    
    first_run = True
    while True:
        if first_run and len(sys.argv) >= 2:
            requirement = " ".join(sys.argv[1:])
            first_run = False
        else:
            first_run = False
            print_log("SYSTEM", "プロンプト（要件・追加指示・修正リクエスト等）を入力してください。", COLOR_SYSTEM, "system")
            try:
                requirement = input(f"{COLOR_USER}プロンプト (exitで終了) > {COLOR_RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nシステムを終了します。")
                sys.exit(0)
                
            if not requirement:
                continue
                
            if requirement.lower() in ["exit", "quit"]:
                print_log("SYSTEM", "システムを終了しました。お疲れ様でした！", COLOR_SYSTEM, "system")
                sys.exit(0)
        
        # マルチエージェントフロー実行
        run_multi_agent_team(requirement)
        print("\n" + "="*70 + "\n")
