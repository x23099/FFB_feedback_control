#!/usr/bin/env bash
# ==============================================================================
# マルチエージェント tmux 画面分割ランチャースクリプト
# ==============================================================================

# 1. tmux の存在確認
if ! command -v tmux &> /dev/null; then
    echo -e "\033[1;31m[エラー] tmux がインストールされていません。\033[0m"
    echo "以下のコマンドを実行して tmux をインストールしてください："
    echo "  sudo apt-get update && sudo apt-get install -y tmux"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${LOG_DIR}"

# ログファイルがなければ空ファイルを生成
touch "${LOG_DIR}/manager.log"
touch "${LOG_DIR}/frontend.log"
touch "${LOG_DIR}/backend.log"
touch "${LOG_DIR}/qa.log"

SESSION_NAME="multi-agent"

# 既存のセッションがあれば破棄
tmux kill-session -t "${SESSION_NAME}" 2>/dev/null

# 2. メインのtmuxセッションを作成 (左ペイン: python3 multi_agent_team.py)
tmux new-session -d -s "${SESSION_NAME}" -c "${SCRIPT_DIR}" "python3 multi_agent_team.py"

# 3. 画面を左右に分割 (左60%, 右40%)
tmux split-window -h -t "${SESSION_NAME}:0.0" -p 40 -c "${SCRIPT_DIR}" "tail -n 30 -f logs/frontend.log"

# 4. 右ペインを上下に3分割 (右上: Front-end, 右中: Back-end, 右下: QA)
tmux split-window -v -t "${SESSION_NAME}:0.1" -p 66 -c "${SCRIPT_DIR}" "tail -n 30 -f logs/backend.log"
tmux split-window -v -t "${SESSION_NAME}:0.2" -p 50 -c "${SCRIPT_DIR}" "tail -n 30 -f logs/qa.log"

# ペインのタイトル設定
tmux select-pane -t "${SESSION_NAME}:0.0" -T "Main Discussion"
tmux select-pane -t "${SESSION_NAME}:0.1" -T "Front-end Log"
tmux select-pane -t "${SESSION_NAME}:0.2" -T "Back-end Log"
tmux select-pane -t "${SESSION_NAME}:0.3" -T "QA Log"

# ペインの枠線にタイトルを表示する設定
tmux set-option -t "${SESSION_NAME}" pane-border-status top
tmux set-option -t "${SESSION_NAME}" pane-border-format "#[fg=cyan,bold] [ #{pane_title} ] #[default]"

# 左ペイン（メイン操作）にフォーカスを当てる
tmux select-pane -t "${SESSION_NAME}:0.0"

# 5. セッションにアタッチ
tmux attach-session -t "${SESSION_NAME}"
