# Phase 4 初回G923物理出力試験メモ

実施日: 2026-09-09

## PCの役割

- ハンコン接続PC: `hsr-Alienware-m16-R2`（`~/yopi_ws`）
  - G923接続
  - `collision_ffb_node`のhardware mode
  - `/collision/ffb_status`監視
- Kobuki PC: `matunuc-NUC13ANHi5`
  - Kobuki、カメラ、`bird_eye.py`、`/odom`
  - 今回の合成FFB試験では未使用

## 条件

- `output_mode=hardware`
- `hardware_armed=true`
- `max_magnitude=0.03`
- `effect_duration_ms=120`
- `WARNING / STEADY / normalized_magnitude=0.03`
- 30 Hzで15 command、約0.5秒間
- 終了時にCLEARを3 command送信

## ソフトウェア結果

0.03・約0.5秒の試験を2回実施した。

| 試行 | WARNING開始 | CLEAR受信 | 継続時間 | 結果 |
|---|---:|---:|---:|---|
| 1 | 1788950715.336704 | 1788950715.838195 | 約501.5 ms | apply継続後に正常停止 |
| 2 | 1788950780.966123 | 1788950781.467512 | 約501.4 ms | apply継続後に正常停止 |

- `requested_magnitude=0.03`、`applied_magnitude=0.03`。
- sequence 0～14のWARNINGを受信し、約33 ms間隔で更新できた。
- sequence 15のCLEARで`action=stop`、`output_active=false`、`applied=0.0`になった。
- 追加CLEARは`action=none`であり、停止状態を維持した。
- Ctrl+C終了時も`reason=shutdown`、`output_active=false`だった。
- `hardware_error`、古いsequence、watchdog timeoutは発生していない。

## 実機所感と判定

- 操作者は振動を感じなかった。
- 操作者確認では、急回転、異音、発熱、Autocenterの異常など、ハンドル側の問題はなかった。
- ROS nodeからevdev backendへのapplyが例外なく完了したことは確認できた。
- `output_active=true`はソフトウェア上の状態であり、G923モーターの実トルク計測ではない。
- 0.03はevdev最大振幅32767に対して約983であり、G923の知覚可能域より弱い可能性がある。
- G923のAC電源状態、デバイス側の実効Gain、低振幅の不感帯も候補である。

したがって、通信・sequence・停止経路はPASS、振動知覚はFAIL、物理effect発生の有無は未確定とする。

## 次の切り分け

1. G923のAC電源接続と、接続時の自己キャリブレーション動作を確認する。
2. 急回転、異音、発熱、Autocenter変化がなかったことを確認する。
3. 安全上の異常がなければ、上限0.05・0.5秒の1イベントへ段階的に進む。
4. 0.05でも知覚できなければ、それ以上へ上げず、Gain、driver、effect形式を診断する。

## 第二段階の準備

- 既定の初回上限0.03は維持した。
- `hardware_initial_test_passed=true`を明示した場合だけ、上限0.05を許可する安全gateを実装した。
- 初回確認の有無にかかわらず、0.05を超えるhardware設定は起動時に拒否する。
- gateの単体試験62件、flake8、pydocstyle、`git diff --check`、2パッケージのclean buildはPASSした。
- このgateを用いて0.05の正弦波・矩形波試験を実施した。

## 0.05矩形波試験結果

- `FF_SQUARE`、0.05、約0.5秒の試験を2回実施した。
- 両試行ともsequence 0で`action=apply`、`requested=0.050`、`applied=0.050`、`pattern=3`、`fault=false`だった。
- 両試行とも約503 ms後のsequence 15で`action=stop`となり、追加CLEARとshutdownでも停止状態を維持した。
- 操作者は振動を知覚できたが、危険通知としては弱いと評価した。
- 同じ強度で矩形波だけ知覚できたため、collision FFB hardware backendの全active patternを矩形波へ変更した。
- 強度上限は0.05のままとし、強度を上げる前に変更後の通常WARNING経路を再検証する。

Phase 4は未完了であり、TTC連動試験には進まない。
