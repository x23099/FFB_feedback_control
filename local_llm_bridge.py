#!/usr/bin/env python3
"""
Local LLM Bridge with Fallback & Toggle Control.

LM Studio, Ollama, vLLM などの OpenAI互換APIを提供するローカルLLMと連携しつつ、
手動トグル(ON/OFF)および自動ヘルスチェック/タイムアウトによるクラウド単体動作への
即時切断（バイパス）機能を備えたモジュール。
"""

import os
import json
import time
import urllib.request
import urllib.error

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_llm_config.json")

def load_config():
    """設定ファイルの読み込み。存在しない場合はデフォルト値を返す。"""
    defaults = {
        "enabled": True,
        "auto_fallback": True,
        "api_base": "http://localhost:1234/v1",
        "model_name": "local-model",
        "timeout_seconds": 2.0,
        "health_check_endpoint": "/models"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            print(f"[LocalLLMBridge] Config load error: {e}. Using defaults.")
    
    # 環境変数での手動オーバーライドチェック (例: USE_LOCAL_LLM=false)
    env_use_local = os.getenv("USE_LOCAL_LLM")
    if env_use_local is not None:
        defaults["enabled"] = env_use_local.lower() in ("true", "1", "yes")

    return defaults

class LocalLLMBridge:
    def __init__(self):
        self.config = load_config()

    def is_enabled(self) -> bool:
        """手動トグルがONになっているか"""
        return self.config.get("enabled", True)

    def check_health(self) -> bool:
        """
        ローカルLLMサーバーへのヘルスチェック(Ping)。
        指定されたタイムアウト内に応答がなければ False を返す。
        """
        if not self.is_enabled():
            return False

        api_base = self.config.get("api_base", "http://localhost:1234/v1").rstrip("/")
        endpoint = self.config.get("health_check_endpoint", "/models")
        url = f"{api_base}{endpoint}"
        timeout = float(self.config.get("timeout_seconds", 2.0))

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LocalLLMBridge-HealthCheck"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def query(self, prompt: str, system_prompt: str = "You are a helpful local assistant.") -> dict:
        """
        ローカルLLMへの問い合わせを実行。
        切断時(OFF)またはヘルスチェック失敗時は status="bypassed" を返し、
        呼び出し側がクラウド単体へ安全に切り替えられるようにする。
        """
        # 1. 手動トグルのチェック
        if not self.is_enabled():
            return {
                "status": "bypassed",
                "reason": "Manual toggle disabled (USE_LOCAL_LLM=false)",
                "content": None
            }

        # 2. 自動ヘルスチェック・タイムアウトの判定
        if self.config.get("auto_fallback", True):
            if not self.check_health():
                return {
                    "status": "bypassed",
                    "reason": f"Local LLM server at {self.config.get('api_base')} is unreachable or timed out.",
                    "content": None
                }

        # 3. OpenAI互換チャットAPI呼び出し
        api_base = self.config.get("api_base", "http://localhost:1234/v1").rstrip("/")
        url = f"{api_base}/chat/completions"
        timeout = float(self.config.get("timeout_seconds", 180.0))
        model = self.config.get("model_name", "google/gemma-4-e4b")


        full_prompt = f"[{system_prompt}]\n\n{prompt}" if system_prompt else prompt
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.3
        }


        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"}
            )
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - start_time
                msg = result["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning_content") or ""
                return {
                    "status": "success",
                    "content": content,
                    "elapsed_sec": round(elapsed, 3),
                    "raw_response": result
                }

        except Exception as e:
            if self.config.get("auto_fallback", True):
                return {
                    "status": "bypassed",
                    "reason": f"Local LLM execution failed: {str(e)}",
                    "content": None
                }
            else:
                return {
                    "status": "error",
                    "reason": str(e),
                    "content": None
                }

if __name__ == "__main__":
    # セルテスト実行
    bridge = LocalLLMBridge()
    print("--- Local LLM Bridge Test ---")
    print(f"Enabled: {bridge.is_enabled()}")
    print(f"Health Check: {bridge.check_health()}")
    
    res = bridge.query("Hello! Briefly state your status.")
    print(f"QueryResult: {res['status']} | Reason/Info: {res.get('reason', 'N/A')}")
