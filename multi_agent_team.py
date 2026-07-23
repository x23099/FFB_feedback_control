#!/usr/bin/env python3
import urllib.request
import json
import sys
import time
import os
import re

# --- 設定値 ---
LOCAL_BRIDGE_URL = "http://localhost:11435/v1/chat/completions"

# 物理モデルの定義 (Google × Anthropic 異種マルチエージェント構成)
MODEL_MANAGER = "gemini-3.6-flash-medium"          # マネージャー (Gemini 3.6 Flash Medium)
MODEL_FRONTEND = "gemini-3.6-flash-low"             # フロントエンド (Gemini 3.6 Flash Low)
MODEL_BACKEND = "antigravity-claude-sonnet-4-6"     # バックエンド (Claude Sonnet 4.6: 高精度ロジック・構造化)
MODEL_QA = "antigravity-claude-opus-4-6-thinking"  # QA (Claude Opus 4.6 Thinking: 最強検証)

# コンソール色出力用のANSIエスケープシーケンス
COLOR_RESET = "\033[0m"
COLOR_MANAGER = "\033[1;34m"   # 太字青
COLOR_FRONT = "\033[1;32m"     # 太字緑
COLOR_BACK = "\033[1;33m"      # 太字黄
COLOR_QA = "\033[1;35m"        # 太字マゼンタ
COLOR_SYSTEM = "\033[1;36m"    # 太字シアン
COLOR_USER = "\033[1;37m"      # 太字白

# --- ログおよびプロジェクトルートの設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # 最上部ルートディレクトリ (/home/robo25/FFB_feedback_control)
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# --- ローカルPC自律探索・操作ツール群 ---
import fnmatch

EXCLUDE_DIRS = {'.git', '__pycache__', 'node_modules', '.antigravity-ide', 'logs', 'brain'}

def resolve_path(path_str):
    """相対パス・絶対パスをプロジェクトルート基準で正しく解決する"""
    if not path_str or path_str == ".":
        return PROJECT_ROOT
    if os.path.isabs(path_str):
        return path_str
    return os.path.abspath(os.path.join(PROJECT_ROOT, path_str))

def tool_search_files(pattern, root_dir=None):
    """指定されたパターン（例: '*.py', '*popup*'）に一致するファイルを探索する"""
    target_dir = resolve_path(root_dir) if root_dir else PROJECT_ROOT
    matches = []
    try:
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for filename in fnmatch.filter(files, pattern):
                rel_path = os.path.relpath(os.path.join(root, filename), PROJECT_ROOT)
                matches.append(rel_path)
                if len(matches) >= 30:
                    break
            if len(matches) >= 30:
                break
        if not matches:
            return f"検索結果: パターン '{pattern}' に一致するファイルは見つかりませんでした。(探索範囲: {target_dir})"
        return f"--- FILE SEARCH RESULTS ('{pattern}' in {target_dir}) ---\n" + "\n".join(matches)
    except Exception as e:
        return f"エラー: ファイル検索中にエラーが発生しました: {e}"

def tool_grep_content(keyword, root_dir=None, file_pattern="*"):
    """コード・ファイルの中身から特定の文字や関数名を検索する（Grep機能）"""
    target_dir = resolve_path(root_dir) if root_dir else PROJECT_ROOT
    results = []
    try:
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for filename in fnmatch.filter(files, file_pattern):
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if keyword.lower() in line.lower():
                                results.append(f"{rel_path}:{line_num}: {line.strip()}")
                                if len(results) >= 20:
                                    break
                except Exception:
                    continue
                if len(results) >= 20:
                    break
            if len(results) >= 20:
                break
        if not results:
            return f"検索結果: キーワード '{keyword}' を含むコードは見つかりませんでした。(探索範囲: {target_dir})"
        return f"--- GREP SEARCH RESULTS ('{keyword}' in {target_dir}) ---\n" + "\n".join(results)
    except Exception as e:
        return f"エラー: 内容検索中にエラーが発生しました: {e}"

def tool_read_file(filepath):
    """ファイルの中身を安全に閲覧する"""
    abs_path = resolve_path(filepath)
    try:
        if not os.path.exists(abs_path):
            return f"エラー: ファイル '{filepath}' (パス: {abs_path}) が存在しません。"
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if len(lines) > 300:
            content = "".join(lines[:300]) + f"\n\n... (※ 300行を超えるため中略。全 {len(lines)} 行)"
        else:
            content = "".join(lines)
        return f"--- FILE CONTENT: {filepath} ---\n{content}\n--- END OF FILE ---"
    except Exception as e:
        return f"エラー: 読み込み失敗: {e}"

def tool_write_file(filepath, content):
    """ファイルを作成・編集して保存する"""
    abs_path = resolve_path(filepath)
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功: ファイル '{filepath}' ({abs_path}) を更新・保存しました。"
    except Exception as e:
        return f"エラー: 保存失敗: {e}"

def tool_list_dir(dirpath=None):
    """指定ディレクトリのファイル一覧を表示する"""
    abs_path = resolve_path(dirpath)
    try:
        if not os.path.exists(abs_path):
            return f"エラー: ディレクトリ '{dirpath}' (パス: {abs_path}) が存在しません。"
        files = os.listdir(abs_path)
        return f"--- DIRECTORY LIST ({abs_path}) ---\n" + "\n".join(files)
    except Exception as e:
        return f"エラー: 一覧取得失敗: {e}"

def execute_tool_call(tool_name, tool_args):
    """ツール名と引数から安全にローカル関数を実行する"""
    if tool_name == "search_files":
        return tool_search_files(tool_args.get("pattern", "*"), tool_args.get("root_dir", "."))
    elif tool_name == "grep_content":
        return tool_grep_content(tool_args.get("keyword", ""), tool_args.get("root_dir", "."), tool_args.get("file_pattern", "*"))
    elif tool_name == "read_file":
        return tool_read_file(tool_args.get("path", ""))
    elif tool_name == "write_file":
        return tool_write_file(tool_args.get("path", ""), tool_args.get("content", ""))
    elif tool_name == "list_dir":
        return tool_list_dir(tool_args.get("path", "."))
    return f"エラー: 未知のツール名 '{tool_name}'"


# --- リアルタイム・トークンカウンター設定 ---
TOKEN_STATS = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "request_count": 0
}
LAST_TOKEN_INFO = {}

def reset_logs():
    """ログファイルおよびトークンカウンターをリセット・初期化する"""
    global TOKEN_STATS, LAST_TOKEN_INFO
    TOKEN_STATS = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "request_count": 0}
    LAST_TOKEN_INFO = {}
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

def print_log(sender, message, color, agent_key="system", show_tokens=True):
    """コンソールへの色つきリアルタイム出力 兼 ログファイルへの記録"""
    timestamp = time.strftime("%H:%M:%S")
    prefix = f"{color}[{timestamp}] {sender}:{COLOR_RESET}"
    print(f"\n{prefix}")
    for line in message.strip().split('\n'):
        print(f"  {line}")
    
    if show_tokens and LAST_TOKEN_INFO and agent_key != "system":
        last_total = LAST_TOKEN_INFO.get("last_total", 0)
        last_prompt = LAST_TOKEN_INFO.get("last_prompt", 0)
        last_comp = LAST_TOKEN_INFO.get("last_comp", 0)
        print(f"\033[1;30m📊 [トークン使用量] リクエスト消費: {last_total:,} tokens (入力: {last_prompt:,} / 出力: {last_comp:,}) | セッション累計: {TOKEN_STATS['total_tokens']:,} tokens (通算{TOKEN_STATS['request_count']}回)\033[0m")
        
    print("-" * 50)
    sys.stdout.flush()
    write_agent_log(agent_key, sender, message)

def estimate_tokens(text):
    """文字数ベースでの簡易トークン数推定（日本語1文字≒1〜1.5トークン）"""
    if not text:
        return 0
    return int(len(text) * 1.1)

def call_bridge_messages(model, messages, temperature=0.7, retries=3):
    """ag-local-bridgeのエンドポイントに会話履歴(messages)配列を送信しトークン数を追跡する"""
    global TOKEN_STATS, LAST_TOKEN_INFO
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
                content = res_data['choices'][0]['message']['content']
                
                # トークン数のパースと計測
                usage = res_data.get("usage", {})
                prompt_t = usage.get("prompt_tokens")
                comp_t = usage.get("completion_tokens")
                
                if prompt_t is None:
                    prompt_t = sum(estimate_tokens(m.get("content", "")) for m in messages)
                if comp_t is None:
                    comp_t = estimate_tokens(content)
                    
                total_t = prompt_t + comp_t
                
                TOKEN_STATS["prompt_tokens"] += prompt_t
                TOKEN_STATS["completion_tokens"] += comp_t
                TOKEN_STATS["total_tokens"] += total_t
                TOKEN_STATS["request_count"] += 1
                
                LAST_TOKEN_INFO = {
                    "last_prompt": prompt_t,
                    "last_comp": comp_t,
                    "last_total": total_t
                }
                
                return content
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

# --- 共通行動規範とフォーマット定義 ---
COMMON_BEHAVIOR_PROMPT = """
【共通行動規範】
1. 前置きの挨拶や雑談、挨拶的なお礼は一切不要です。直ちに業務内容に入ってください。
2. 全員敬語で会話してください。
3. 感情や人の人格ではなく、設計・コード・判断を客観的に評価・批判してください。
4. 不明点を推測で埋めず、仮定として明示してください。
5. 反対意見を述べる場合は、必ず具体的な根拠と「代替案」を提示してください。
6. 必要以上に相手を褒めたり同意したりせず、結論、根拠、提案の順で話してください。
7. 回答は以下の形式を参考に構造化して出力してください。

【標準出力フォーマット】
結論: (結論を短く明記)
根拠: (理由や技術的背景)
問題点: (懸念事項やバグ、矛盾)
提案: (具体策・代替案・実装コード)
確認事項: (他担当者やユーザーへの確認点)

【利用可能なローカルPC自律操作ツール】
ローカルファイルの検索・閲覧・編集が必要な場合は、以下のJSON形式を回答内に出力してください。
システムが自動的にコマンドを実行し、結果を返送します。

- ファイル名パターン検索:
{"tool": "search_files", "pattern": "*.py"}

- ファイル内容キーワード検索 (Grep):
{"tool": "grep_content", "keyword": "検索文字列"}

- ファイルの閲覧:
{"tool": "read_file", "path": "相対パス"}

- ファイルの作成・編集保存:
{"tool": "write_file", "path": "相対パス", "content": "内容"}

- ディレクトリ一覧表示:
{"tool": "list_dir", "path": "ディレクトリパス"}
"""

def parse_manager_response(response_text):
    """マネージャーの返答からJSON部分を極力安全・頑丈に抽出してパースする"""
    cleaned = response_text.strip()
    
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
        
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0).strip()
        
    try:
        parsed = json.loads(cleaned)
        
        # 質問・要約が空文字だった場合の二重フォールバック安全装置
        if not parsed.get("question") or not str(parsed.get("question")).strip():
            raw_clean = re.sub(r'```[a-z]*', '', response_text).replace('```', '').strip()
            parsed["question"] = raw_clean if raw_clean else "内容について補足や追加のご要望はございますか？"
            
        if not parsed.get("summary") or not str(parsed.get("summary")).strip():
            parsed["summary"] = "要件の整理・検討を実施中"

        if parsed.get("is_plan_complete", False):
            plan_content = parsed.get("final_plan", "").strip()
            if not plan_content or len(plan_content) < 30:
                parsed["is_plan_complete"] = False
                parsed["question"] = "計画書の詳細な内容が不足しています。具体的仕様を決定してください。"
        return parsed
    except Exception:
        text_only = re.sub(r'```[a-z]*', '', response_text).replace('```', '').strip()
        return {
            "is_plan_complete": False,
            "summary": "要件の確認・探索中",
            "question": text_only if text_only else "指示内容について詳しく教えてください。",
            "options": [
                "1. 上記の方向性で進める",
                "2. 別の代替案を検討する"
            ],
            "final_plan": ""
        }

def manager_user_discussion_phase(initial_requirement):
    """フェーズ1: マネージャーとユーザーの対話型計画策定"""
    print_log("SYSTEM", f"【フェーズ1】マネージャーとの対話を開始します。\n初期要求:\n{initial_requirement}", COLOR_SYSTEM, "system")
    
    system_prompt = (
        "あなたは開発プロジェクトの統括マネージャー（冷静な戦略家・現実主義者）です。\n\n"
        "【役割と思考傾向】\n"
        "- 目的、優先順位、全体整合性を最優先します。\n"
        "- 【最重要ルール】不足している情報を自分の推測で埋めて計画書を勝手に完成させてはいけません。\n"
        "- 必ずユーザーに質問・確認を行い、仕様の曖昧さや認識のズレが完全になくなるまで対話・議論を継続してください。\n"
        "- ユーザーとの対話を通じて十分な情報が揃い、認識が完全に一致したと確信できた場合にのみ、議論のまとめとして `is_plan_complete: true` に設定し、`final_plan`（計画書）を作成してください。\n\n"
        + COMMON_BEHAVIOR_PROMPT + "\n\n"
        "【フェーズ1専用ルール】\n"
        "ユーザーと対話して計画を固めます。完成と判断した際、`final_plan` には必ず以下の10項目で構成される標準計画書テンプレート形式で出力してください。\n\n"
        "【必須計画書フォーマット (final_planの記述形式)】\n"
        "# 計画書\n"
        "## 1. 目的\n- 何を実現したいか:\n- 期待する効果:\n- 成功条件:\n"
        "## 2. 背景\n- 現状:\n- 課題:\n- 変更理由:\n"
        "## 3. 要件\n### 必須要件\n- \n### できれば欲しい要件\n- \n### 非要件\n- 性能/セキュリティ/保守性/UI/UX:\n"
        "## 4. 変更範囲\n- 対象:\n- 対象外:\n"
        "## 5. 実装方針\n- 方針:\n- 採用理由:\n- 代替案と不採用理由:\n"
        "## 6. タスク分割\n| 順番 | 担当 | タスク | 入力 | 出力 | 完了条件 |\n|---|---|---|---|---|---|\n"
        "## 7. 受け入れ条件\n- \n"
        "## 8. リスク\n| リスク | 影響 | 対策 |\n|---|---|---|\n"
        "## 9. 未確定事項\n- \n"
        "## 10. 承認\n- あなたの確認:\n- マネージャー確認:\n- エンジニア確認:\n\n"
        "必ず以下の純粋なJSONフォーマットのみを出力してください。\n\n"
        "{\n"
        '  "is_plan_complete": false,\n'
        '  "summary": "これまでの決定事項・要件の要約",\n'
        '  "question": "ユーザーへの質問本文 (選択肢を添付)",\n'
        '  "options": [\n'
        '    "1. 選択肢Aの説明",\n'
        '    "2. 選択肢Bの説明"\n'
        "  ],\n"
        '  "final_plan": "" // is_plan_completeが true の場合のみ、上記の10項目テンプレート形式で記述\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"初期要件:\n{initial_requirement}"}
    ]

    while True:
        raw_res = call_bridge_with_tools_messages(MODEL_MANAGER, messages)
        data = parse_manager_response(raw_res)

        if data.get("is_plan_complete", False) and data.get("final_plan", "").strip():
            final_plan = data.get("final_plan").strip()
            
            with open("plan.md", "w", encoding="utf-8") as f:
                f.write(final_plan)

            handoff_md = f"""# 実装依頼 (Handoff)

## 目的
{initial_requirement}

## 参照計画書
- ファイル名: plan.md

## 完了時の成果物
- コード差分
- テスト結果
- 変更点の要約

## 確認したい点
- 実装方針に不明点があれば先に質問すること
"""
            with open("handoff.md", "w", encoding="utf-8") as f:
                f.write(handoff_md)

            decision_md = f"""# 決定履歴 (Decision Log)

- 初期要件: {initial_requirement}
- 決定要約: {data.get('summary', '')}
- ステータス: ユーザー承認待ち
"""
            with open("decision_log.md", "w", encoding="utf-8") as f:
                f.write(decision_md)

            output_file = "multi_agent_output.md"
            draft_md = f"""# インタラクティブ開発マルチエージェント 開発計画書 (案)

## 👑 確定開発計画書 (マネージャー提案 / plan.md)
{final_plan}

---
*※ 承認待ち状態です。Antigravity等で 'plan.md' または 'multi_agent_output.md' を確認し、ターミナルで [y/yes] または修正指示を入力してください。*
"""
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(draft_md)

            print_log("SYSTEM", f"📄 計画書を 'plan.md', 'handoff.md', 'decision_log.md', '{output_file}' に出力保存しました。", COLOR_SYSTEM, "system")
            print_log("マネージャー", f"全体の内容は Antigravity で 'plan.md' または '{output_file}' を開いてご確認ください。\n要約: {data.get('summary', '計画書を作成しました。')}", COLOR_MANAGER, "manager")
            write_agent_log("manager", "Manager (高精度開発計画書)", final_plan)
            
            print_log("マネージャー", "上記計画書の内容で実装を開始してよろしいでしょうか？", COLOR_MANAGER, "manager")
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
                clean_assistant_msg = json.dumps(data, ensure_ascii=False)
                messages.append({"role": "assistant", "content": clean_assistant_msg})
                messages.append({"role": "user", "content": f"計画書の修正指示: {confirm}"})
                continue

        summary = data.get("summary", "")
        question = data.get("question", "")
        options = data.get("options", [])

        if summary:
            print_log("マネージャー (要約)", summary, COLOR_MANAGER, "manager")
        
        msg_content = question
        if options:
            msg_content += "\n\n【選択肢】\n" + "\n".join(options) + "\n※ 番号を選択するか、自由に入力(Other)してください。"
        
        print_log("マネージャー (質問)", msg_content, COLOR_MANAGER, "manager")

        try:
            user_input = input(f"{COLOR_USER}あなた (回答を入力) > {COLOR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "1"

        if not user_input:
            user_input = "1 (デフォルト選択)"

        clean_assistant_msg = json.dumps(data, ensure_ascii=False)
        messages.append({"role": "assistant", "content": clean_assistant_msg})
        messages.append({"role": "user", "content": f"ユーザーの回答: {user_input}"})


def extract_terminal_summary(agent_name, full_output):
    """ターミナルのログ肥大化を防ぐため、出力結果から要約・結論のみを抽出してターミナル表示用にする"""
    lines = full_output.strip().split('\n')
    summary_lines = []
    in_code_block = False
    
    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                summary_lines.append(f"  [※ {agent_name} の実装コード(詳細)は multi_agent_output.md およびログファイルに保存されました]")
            continue
        if not in_code_block:
            summary_lines.append(line)
            
    summary_text = "\n".join(summary_lines[:20]) # ターミナル表示は最大20行程度に抑える
    if len(lines) > 20:
        summary_text += f"\n...\n(※ 全文・詳細コードは multi_agent_output.md または logs/ を参照してください)"
    return summary_text


def call_bridge_with_tools_messages(model, messages, temperature=0.7, max_tool_turns=5):
    """会話履歴 (messages) を保持しながらツール呼び出し(Tool Calling)を自動実行・継続する"""
    for turn in range(max_tool_turns):
        res = call_bridge_messages(model, messages, temperature)
        
        match = re.search(r'\{\s*"tool"\s*:\s*"[^"]+"\s*,.*?\n?\}', res, re.DOTALL)
        if not match:
            match = re.search(r'\{[^{}]*"tool"[^{}]*\}', res)

        if match:
            tool_str = match.group(0)
            try:
                tool_data = json.loads(tool_str)
                tool_name = tool_data.get("tool")
                tool_result = execute_tool_call(tool_name, tool_data)
                
                print_log("SYSTEM (Tool Call)", f"🛠️ マネージャー自律ツール実行 [{tool_name}]:\n{tool_str}\n\n実行結果:\n{tool_result[:200]}...", COLOR_SYSTEM, "system")
                
                messages.append({"role": "assistant", "content": res})
                messages.append({"role": "user", "content": f"【ツール自動実行結果 ({tool_name})】\n{tool_result}\n\n上記の結果を踏まえて質問・計画策定を継続してください。"})
                continue
            except Exception as e:
                pass
                
        return res
    return res


def call_bridge_with_tools(model, system_prompt, user_prompt, temperature=0.7, max_tool_turns=5):
    """ツール呼び出し(Tool Calling)をパースしてローカル関数を実行し、会話を継続する"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    return call_bridge_with_tools_messages(model, messages, temperature, max_tool_turns)


def engineering_and_qa_phase(final_plan):
    """フェーズ2: エンジニア作業事前協議、コード製作、およびQA検証"""
    print_log("SYSTEM", "【フェーズ2】確定計画書(plan.md)が渡されました。エンジニアチームが作業内容の事前協議を開始します。", COLOR_SYSTEM, "system")
    conversation_logs = []

    # ----------------------------------------------------
    # ステップ 0: 各エンジニアによる作業事前協議（何をどう分担して進めるか）
    # ----------------------------------------------------
    print(f"{COLOR_SYSTEM}🤝 [事前協議] フロント・バック・QAが作業分担とインターフェースを協議中...{COLOR_RESET}")
    alignment_sys = (
        "あなたは開発チームの一員です。確定計画書をもとに、以下の内容をチームとユーザーに簡潔に報告してください。\n"
        "1. あなたの役割での具体的作業内容\n"
        "2. 入力と出力の境界条件 (API/データフォーマット/UI状態)\n"
        "3. 他担当者へ確認・共有したい点\n"
        + COMMON_BEHAVIOR_PROMPT
    )
    
    front_align = call_bridge_with_tools(MODEL_FRONTEND, alignment_sys, f"確定計画書:\n{final_plan}\n\n担当: フロントエンド")
    print_log("フロントエンド (事前協議)", extract_terminal_summary("フロントエンド", front_align), COLOR_FRONT, "frontend")
    
    back_align = call_bridge_with_tools(MODEL_BACKEND, alignment_sys, f"確定計画書:\n{final_plan}\nフロント事前提案:\n{front_align}\n\n担当: バックエンド")
    print_log("バックエンド (事前協議)", extract_terminal_summary("バックエンド", back_align), COLOR_BACK, "backend")

    qa_align = call_bridge_with_tools(MODEL_QA, alignment_sys, f"確定計画書:\n{final_plan}\nフロント案:\n{front_align}\nバック案:\n{back_align}\n\n担当: QA")
    print_log("QAエンジニア (事前協議)", extract_terminal_summary("QAエンジニア", qa_align), COLOR_QA, "qa")

    print_log("SYSTEM", "✅ 事前協議が完了しました。各エンジニアがコード実装および詳細検証に入ります。", COLOR_SYSTEM, "system")
    time.sleep(2)

    # ----------------------------------------------------
    # ステップ 1: フロントエンド実装設計
    # ----------------------------------------------------
    front_sys = (
        "あなたはフロントエンドエンジニアです。確定計画書と事前協議をもとに、\n"
        "UI/UX構造、コンポーネント構成、フロントエンドの具体的な実装コード（Python/HTML/JS等）およびコード解説を作成してください。\n"
        "必要に応じて search_files や grep_content, read_file ツールを使用してローカルファイルを閲覧・検索・編集してください。\n"
        + COMMON_BEHAVIOR_PROMPT
    )
    print(f"{COLOR_SYSTEM}  - [1/3] フロントエンドエンジニアがコード・設計を作成中...{COLOR_RESET}")
    front_output = call_bridge_with_tools(MODEL_FRONTEND, front_sys, f"確定計画書:\n{final_plan}\n協議ログ:\n{front_align}")
    write_agent_log("frontend", "Frontend Implementation", front_output)
    print_log("フロントエンド (実装要約)", extract_terminal_summary("フロントエンド", front_output), COLOR_FRONT, "frontend")
    conversation_logs.append(("Front-end (コード・設計)", front_output))

    # ----------------------------------------------------
    # ステップ 2: バックエンド実装設計
    # ----------------------------------------------------
    back_sys = (
        "あなたはバックエンドエンジニアです。確定計画書と事前協議をもとに、\n"
        "システムロジック、データ構造、API、バックエンドの具体的な実装コード（Python等）およびコード解説を作成してください。\n"
        "必要に応じて search_files や grep_content, read_file, write_file ツールを使用してローカルファイルを閲覧・検索・編集してください。\n"
        + COMMON_BEHAVIOR_PROMPT
    )
    print(f"{COLOR_SYSTEM}  - [2/3] バックエンドエンジニアがコード・設計を作成中...{COLOR_RESET}")
    time.sleep(2)
    back_output = call_bridge_with_tools(MODEL_BACKEND, back_sys, f"確定計画書:\n{final_plan}\n協議ログ:\n{back_align}\nフロント実装:\n{front_output}")
    write_agent_log("backend", "Backend Implementation", back_output)
    print_log("バックエンド (実装要約)", extract_terminal_summary("バックエンド", back_output), COLOR_BACK, "backend")
    conversation_logs.append(("Back-end (コード・設計)", back_output))

    # ----------------------------------------------------
    # ステップ 3: QAデバッグ・セキュリティ検証
    # ----------------------------------------------------
    qa_sys = (
        "あなたはQA・デバッグエンジニアです。\n"
        "フロントエンドとバックエンドのコード・設計案を深くレビューし、\n"
        "1. 重大度分類 (Critical / High / Medium / Low)\n"
        "2. バグ・エッジケース・セキュリティ脆弱性・接続不整合の指摘\n"
        "3. 具体的な修正コード案\n"
        "を含めた検証報告書を作成してください。\n"
        "必要に応じて read_file ツール等で実装ファイルを確認してください。\n"
        + COMMON_BEHAVIOR_PROMPT
    )
    qa_prompt = (
        f"確定開発計画書:\n{final_plan}\n\n"
        f"フロントエンド実装:\n{front_output}\n\n"
        f"バックエンド実装:\n{back_output}"
    )
    print(f"{COLOR_SYSTEM}  - [3/3] QAエンジニアがコードを検証・デバッグ中...{COLOR_RESET}")
    time.sleep(2)
    qa_report = call_bridge_with_tools(MODEL_QA, qa_sys, qa_prompt)
    write_agent_log("qa", "QA Debug Report", qa_report)
    print_log("QAエンジニア (検証要約)", extract_terminal_summary("QAエンジニア", qa_report), COLOR_QA, "qa")
    conversation_logs.append(("QA (デバッグ・検証報告)", qa_report))

    # ----------------------------------------------------
    # ステップ 4: マネージャーによる最終統括
    # ----------------------------------------------------
    manager_sys = (
        "あなたは統括マネージャーです。エンジニアのコードとQAの検証結果を確認し、\n"
        "全体の成果物（確定仕様、完成コード、QA検証結果、今後の運用方針）を納品レポートとしてまとめてください。\n"
        + COMMON_BEHAVIOR_PROMPT
    )
    manager_prompt = f"計画書:\n{final_plan}\n\nQA統合レポート:\n{qa_report}"
    print(f"{COLOR_SYSTEM}マネージャーが最終納品レポートを作成中...{COLOR_RESET}")
    final_output = call_bridge(MODEL_MANAGER, manager_sys, manager_prompt)
    write_agent_log("manager", "Final Summary Report", final_output)
    print_log("マネージャー (最終総括)", extract_terminal_summary("マネージャー", final_output), COLOR_MANAGER, "manager")

    # 成果物の書き出し
    report_md = f"""# インタラクティブ開発マルチエージェント 成果物レポート

## 👑 確定開発計画書 (マネージャー & ユーザー合意)
{final_plan}

---

## 🤝 事前作業協議ログ (エンジニアチーム)
### フロントエンド事前方針:
{front_align}

### バックエンド事前方針:
{back_align}

### QA事前確認方針:
{qa_align}

---

## 🎨 フロントエンド実装・設計
{front_output}

---

## ⚙️ バックエンド実装・設計
{back_output}

---

## 🔍 QAデバッグ・セキュリティ検証報告
{qa_report}

---

## 🏆 最終納品レポート (マネージャー統括)
{final_output}
"""
    output_file = "multi_agent_output.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    print_log("SYSTEM", f"✨ 全工程が完了しました！成果物および全エンジニアのフル出力・コードは '{output_file}' に保存されました。", COLOR_SYSTEM, "system")


def run_multi_agent_team(initial_requirement):
    """メイン実行エントリーポイント"""
    reset_logs()
    
    # フェーズ1: マネージャーとユーザーによる計画確定
    final_plan = manager_user_discussion_phase(initial_requirement)
    
    # フェーズ2: エンジニアチームによる協議・製作・検証
    engineering_and_qa_phase(final_plan)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        req = " ".join(sys.argv[1:])
    else:
        print_log("SYSTEM", "マルチエージェント開発システムを開始します。（終了するには 'exit' または 'quit' と入力）", COLOR_SYSTEM, "system")
        print_log("SYSTEM", "プロンプト（要件・追加指示・修正リクエスト等）を入力してください。", COLOR_SYSTEM, "system")
        try:
            req = input(f"{COLOR_USER}プロンプト入力 > {COLOR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)
            
    if not req or req.lower() in ["exit", "quit"]:
        print_log("SYSTEM", "システムを終了します。", COLOR_SYSTEM, "system")
        sys.exit(0)

    run_multi_agent_team(req)
