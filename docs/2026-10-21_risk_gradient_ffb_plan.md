# リスク勾配の力覚提示（抵抗型）実装計画

作成日: 2026-10-21  
対象:
- `/home/robo25/FFB_feedback_control/FFB_feedback_control`（指令・アダプタ）
- `/home/robo25/theta_ws/RICHO-theta`（認識・リスク・勾配計算）

> **実装状況（2026-11-13）**: Phase 1（勾配計算）、Phase 2（`direction` 伝搬）、Phase 3（`FF_CONSTANT` backend）、Phase 4（`bird_eye` 接続・記録）は実装・単体テスト済み。**synthetic/replay dry-run と camera-side synthetic-track dry-run は PASS**。実カメラ動画と G923 実機確認は未実施。
>
> 関連コミット: FFB `5ccd371`（実装）、`5f5caf6` / `f28bebd`（計画書）、`21a5b2c`（設定）、RICHO `41f9a8b`（Phase 2）、`74c87f0`（Phase 4）、`913d29c`（replay status）。
>
> 本書は実装に合わせて符号規約とPhase 4の方式を更新済み。残作業の設計メモとして維持する。

---

## 1. 目的と方針

差動2輪ロボットの遠隔操縦において、衝突リスクの**大きさ**だけでなく
**左右の回避余裕の差（勾配）**を操舵反力に写像する。

- 方式: **抵抗型**（危険側を重くする。安全側への誘導トルクは出さない）
- 手動権: 操縦者が常に保持する。力覚は操作を禁止しない
- 新規性: 空間のポテンシャルではなく、**操作入力 ω に対するリスク感度**を提示する点
- 鮮度検証（challengeトークン）は**新規性ではなく安全設計**として扱う

---

## 2. 現状（2026-11-13 更新）

| 項目 | 現状 | 場所 |
|---|---|---|
| 指令フィールド | `risk_level` / `pattern` / `normalized_magnitude`(0..1) / `direction`(-1/0/+1) | `src/oit_interfaces/msg/CollisionFfbCommand.msg` |
| 出力effect | `FF_PERIODIC`（FF_SQUARE）と `FF_CONSTANT`（符号付き定常力） | `src/oit/oit/collision_ffb_backend.py` |
| 持続時間 | 120 ms の有限effectを約50 msで再トリガー | 同上 / `effect_duration_ms` |
| 強度上限 | 設定 `max_magnitude=0.05`、絶対上限 0.25 | `src/oit/oit/collision_ffb_node.py` |
| 方向ゲート | `direction_enabled=false` が既定。hardware のみ方向出力を許可 | `src/oit/oit/collision_ffb_node.py` |
| 物理符号 | `constant_direction_sign`（±1）で実機校准 | `src/oit/oit/collision_ffb_backend.py` |
| デバイス能力 | `FF_CONSTANT` / `FF_SPRING` / `FF_PERIODIC` 対応 | `implementation_plan.md` 2.2 |
| 操舵角 | `/handle/steering_norm`, `/handle/steering_angle_deg` を配信済み | `RICHO-theta/src/handle.py` |

**結論**: 指令への方向追加、`FF_CONSTANT` backend、認識側の勾配接続（Phase 4）、
synthetic/replay dry-run、camera-side synthetic-track dry-run は完了。
残るのは実カメラ動画での確認と、G923 実機での方向・強度確認（Phase 5）。

---

## 3. 全体構成

```
[カメラ側PC]
  コーン位置（床交点方式, 既存）
        ↓
  追跡＋観測品質ゲート（既存）
        ↓
  TTC・リスク判定（既存）
        ↓
  ★勾配計算（Phase 1 実装済み）
     ω−Δ / ω / ω+Δ の3本の予測経路を同一スナップショットで評価
        ↓
  /collision/ffb_command に magnitude と direction を付加（Phase 2 実装済み）
        ↓ ROS 2 DDS
[操縦側PC]
  collision_ffb_node（安全ゲート: 期限・watchdog・上限・direction検証）
        ↓
  ★FF_CONSTANT（符号付き定常力、Phase 3 実装済み）
        ↓
  G923
```

---

## 4. 勾配の定義と計算

### 4.1 定義

操舵入力 `ω` に対するリスク `R(ω)` を、予測経路上の最小TTCから定義する。

```
R(ω) = 1 / clamp(TTC(ω), T_MIN, T_MAX)
g = ( R(ω+Δ) − R(ω−Δ) ) / (2Δ)
```

- `ω > 0` = 左旋回（ROS REP-103。`bird_eye.py` の操舵入力もこの規約）
- `g > 0` → 左に切るとリスク増（**左が危険**）
- `g < 0` → 右に切るとリスク増（**右が危険**）
- `Δ = 0.10〜0.20 rad/s`（人が0.3〜0.5秒で切る量）
- `T_MIN = 0.1 s`, `T_MAX = 10 s`（無限大のクランプ）

Phase 1 の実装では、`TTC(ω)` の代理として
`assess_path_collision()` の `path_eta_sec`（経路に沿った到達時間）を用いる。
厳密なTTC再計算は障害物速度ベクトルが必要なため、将来拡張とする。

### 4.2 正規化と平滑化

```
ĝ = clamp(g / G_SCALE, -1, +1)
ĝ = EMA(ĝ, α=0.2〜0.3)          # 100〜200 ms
if |ĝ| < 0.1: ĝ = 0             # デッドバンド（直進・左右対称時）
if risk_level in {CLEAR, PATH}: ĝ = 0
```

- `ĝ > 0` = 左が危険、`ĝ < 0` = 右が危険
- `G_SCALE` は予備実験で調整（初期値 `1.0 [rad/s per 1/s]` 程度）

### 4.3 速度・後退の扱い

- `|v| < 0.02 m/s`: 予測経路が退化するため、旋回のみのリスク評価に切り替える
  （または勾配を0にして大きさのみ提示）
- `v < 0`（後退）: `ω` とヨー方向の対応が反転するため、勾配の符号を反転
- 同一制御周期の**1スナップショット**で3本の経路を評価する（経路ごとに再検出しない）

---

## 5. 力覚への写像（抵抗型）

### 5.1 基本式

```
base = 0.25 (WARNING) / 0.40 (CRITICAL) / 0.15 (UNKNOWN, pulse)
左切れの抵抗 = base × (1 + k·ĝ)     # ĝ>0（左が危険）のとき増加
右切れの抵抗 = base × (1 − k·ĝ)     # ĝ>0 のとき減少
```

- `k = 0.6` 程度（予備実験で調整）
- 0..`max_magnitude` にクランプ
- 「大きさだけ」の条件では `ĝ=0` として同じ式で比較できる（実験条件の統制が容易）

> 実装上の注記: Phase 2 では `(1 ± k·ĝ)` の大きさ変調はまだ送らず、
> `ĝ` の符号を `direction` に縮約し、`normalized_magnitude` は左右で共通値を使う。
> 大きさ変調（`k`）は実機実験の条件として追加する。

### 5.2 実装方式

`FF_CONSTANT` の符号付き定常力とする。方向は `direction` フィールドで指定。

- `direction = -1`: 左切れを重くする（右向きトルク）
- `direction = +1`: 右切れを重くする（左向きトルク）
- `direction = 0`: 従来の周期振動（後方互換）

Phase 3 の実装詳細:

- `ff.Constant.level` は符号付き int16。`direction` は level の符号で表現し、
  effect の `direction` フィールドは 0 のままとする。
- `constant_direction_sign`（既定 `+1`）で実機の物理方向を反転できる。
  実機確認後に `-1` へ変更する。
- `direction_enabled=false`（既定）では方向出力を拒否する。
  hardware モードでは node が `direction` を0に丸めて警告する。
- periodic ↔ constant の切替時は effect slot を stop/erase して再確保する。
- 有限再生（`Replay(120ms, 0)`）と 50 ms 周期の再トリガーは維持する。

`FF_SPRING` の左右非対称係数でも表現できるが、以下理由で `FF_CONSTANT` を第一候補とする。

- 現行の「強度＋パターン」構造を保ちやすい
- スプリングは常に中心へ戻す力が働き、操縦者が角度を保持したい場面で邪魔になる
- 符号と大きさの検証が単純（安全ゲートに乗せやすい）

### 5.3 指令の拡張（実装済み）

```diff
  uint8 pattern
  bool active
  float32 normalized_magnitude
+ int8 direction            # -1 / 0 / +1
  string reason
```

`CollisionFfbStatus.msg` にも `int8 direction`（適用方向）を追加した。
`output_active=false` のときは 0 を報告する。

後方互換:
- `direction` 未設定（0）なら従来どおり `FF_PERIODIC`
- 非アクティブ（CLEAR/PATH）と PULSE は `direction=0` を必須とする
- 新旧メッセージの混在は禁止（両PCで `oit_interfaces` を再ビルド）

代替案として `float32 signed_torque`（符号と強度を1フィールド）も可能だが、
`direction` 分離案の方が既存の `normalized_magnitude` 検証（0..1）を壊さない。
`ĝ` は指令には載せず、カメラ側の記録に残す方針とする。

---

## 6. 変更対象

### 6.1 `oit_interfaces/msg/CollisionFfbCommand.msg`（実装済み）
- `int8 direction` を追加
- `CollisionFfbStatus.msg` にも `int8 direction` を追加

### 6.2 `src/oit/oit/collision_ffb_backend.py`（実装済み）
- `build_constant_effect(ff, ecodes, *, effect_id, direction, normalized_magnitude, duration_ms)` を追加
- `FF_CONSTANT` のcapability検査
  - `direction_enabled=true` の hardware モードでは起動時に必須化
  - 初回の constant apply 時にも再確認
- `apply()` を `apply(magnitude, pattern, direction=0)` に拡張
  - `pattern in (STEADY, STEADY_HOLD)` かつ `direction != 0` → `FF_CONSTANT`
  - それ以外 → 従来の `FF_PERIODIC`
- 有限再生（`Replay(duration_ms, 0)`）と stop/erase は維持
- `constant_direction_sign` と effect種別の切替（slot再確保）を追加

### 6.3 `src/oit/oit/collision_ffb_node.py`（実装済み）
- `direction` の検証（-1/0/+1 以外は拒否）
- `direction_enabled`（既定 `false`）と `constant_direction_sign`（既定 `+1`）を追加
- `max_magnitude` クランプは従来どおり
- watchdog・期限・challenge検証は変更しない
- `direction` を status とログに残す（実験時の解析用）
- dry-run では `direction_enabled` に関係なく direction を伝搬・記録する
- hardware で `direction_enabled=false` の場合は direction を0に丸めて警告する

### 6.4 `RICHO-theta`（カメラ側）

**Phase 1（実装済み）**
- `collision_risk.py` に `evaluate_candidate_steering()` を追加
  - `predict_unicycle_path(v, ω−Δ / ω / ω+Δ)` → `assess_path_collision()` × 3
  - `path_eta_sec` を TTC 代理として `R` を計算
  - 勾配 `g`、正規化 `ĝ`、左右のリスク・ETA・corridor を返す
  - `path_factory` 注入により、呼び出し側で予測パラメータを差し替え可能
    （Phase 4 では実効ヨーを中心に raw unicycle の候補経路を生成）
- `SteeringGradientFilter`（EMA・デッドバンド・CLEAR/無効時リセット）を追加
- `gradient_to_direction()` を追加
  - `ĝ > +0.1` → `-1`（**左が危険**、左切りを重くする）
  - `ĝ < -0.1` → `+1`（右が危険、右切りを重くする）
  - それ以外 → `0`

**Phase 2（実装済み）**
- `collision_ffb_publisher.py` に `publish_risk(..., direction=0)` を追加
  - 非アクティブと PULSE は強制的に0
  - `collision_ffb_direction` を記録CSVに追加
- `collision_ffb_relay.py` で `direction` を転送・検証
  - 範囲外と inactive時の非ゼロ方向を拒否
  - diagnostics に `intent_direction` を追加

**Phase 4（実装済み）**
- `bird_eye.py` の `draw_predicted_path_on_bev()` から
  `update_steering_gradient()` を呼び、`publish_collision_ffb()` で
  `publish_risk(direction=...)` に接続
- `collision_ffb_direction_enabled`（カメラ側、既定0）を追加
- 勾配の中心は `last_prediction_angular_radps`（表示経路の実効ヨー）とし、
  候補はその `±Δ` を **raw unicycle** で評価する
  - 表示用のコマンド→ヨーリマップは中心経路にのみ適用済み
  - 候補にリマップを再適用すると、低速度・小舵角で勾配が潰れるため
- `remap_command_angular()` をモジュール関数に切り出し、
  `predict_path_points()` とオフラインreplayで共有
- 記録CSVに以下を追加
  - `collision_ffb_direction`
  - `collision_ffb_gradient_raw`
  - `collision_ffb_gradient_normalized`
  - `collision_ffb_gradient_filtered`
  - `collision_ffb_gradient_reason`
- `replay_collision_ffb_commands.py` で記録済み `direction` を再送
- 設定に `collision_ffb_gradient_*`（Δ, G_SCALE, EMA, deadband,
  prediction_time, step）を追加

> Phase 4 の単体テストで、`Δ` をコマンド空間に置くと表示リマップの圧縮で
> 勾配が0になりやすいことを確認した。そのため `Δ` は実効ヨー空間に置く。

---

## 7. 安全要件

1. **fail closed**: 不正値・期限切れ・watchdog・例外では出力しない（既存を維持）
2. **有限effect**: 定常力も120 msで自動停止し、50 ms周期で再トリガー
3. **上限**: 設定上限（既定0.05）と絶対上限（0.25）の二重制限
4. **ハードウェア-arm**: `hardware_armed` / `challenge_hardware_armed` の明示が必須（既存）
5. **方向ゲート**: `direction_enabled=true` を明示しない限り hardware では方向出力しない（既定 `false`）
6. **単一writer**: `FfbWriterLock` を維持
7. **方向の整合性**: 非アクティブ（CLEAR/PATH）と PULSE は `direction=0` を必須とする
8. **方向の実機確認**: 停止状態で `direction=-1/+1` を短時間だけ出し、左右の向きを確認
9. **勾配の暴れ対策**: デッドバンド、EMA、CLEAR時のゼロ、`|ĝ|` のクランプ

---

## 8. テスト計画

### 8.1 単体（Phase 1〜3 実装済み）

**勾配**
- 左右対称なら `g=0`
- 左危険なら `g>0`（`direction=-1`）、右危険なら `g<0`（`direction=+1`）
- `v=0` で勾配0、後退時に符号と左右ラベルが反転
- EMA・デッドバンド・CLEAR/PATH時のリセット
- `path_factory` が `ω−Δ`, `ω`, `ω+Δ` の3回呼ばれること

**メッセージ・安全性**
- `direction` の検証（-2, 2, 1.5, bool, None を拒否）
- 非アクティブと PULSE は `direction=0` 必須
- status の `direction` が applied direction になること
- `direction_enabled=false` の hardware で0に丸められること

**backend**
- `FF_CONSTANT` effect の構築（符号・強度・120ms）
- `direction=0` で従来と同一の periodic effect になること
- periodic ↔ constant の切替で slot を再確保すること
- `direction_enabled=true` で `FF_CONSTANT` 非対応デバイスを起動時に拒否すること
- `constant_direction_sign` で level の符号が反転すること

**relay / publisher**
- `direction` の転送、記録CSV、diagnostics
- 範囲外・inactive時の非ゼロ方向を拒否
- PULSE で direction を0にすること

**bird_eye 接続（Phase 4）**
- 左障害物で `direction=-1`、右障害物で `direction=+1`
- `collision_ffb_direction_enabled=0`、トラックなし、無効測定でリセット
- CLEAR / PATH で勾配0
- `remap_command_angular()` と `predict_path_points()` の一致
- `publish_collision_ffb()` が direction と gradient 記録を渡す
- replay が記録済み direction を再送する

### 8.2 dry-run（synthetic/replay は PASS、実カメラは未実施）

**synthetic publisher（30 Hz、G923なし）**
- `WARNING` / `STEADY` / `direction=-1` → `apply`、`status.direction=-1`
- `WARNING` / `STEADY` / `direction=+1` → `apply`、`status.direction=+1`
- `UNKNOWN` / `PULSE` / `direction=+1` → `STOP` / fault
  （`pulse_request_requires_zero_direction`）
- `CLEAR` → `direction=0`

**replay（合成CSV、G923なし）**
- Decision: **PASS**
- fault 0、最大適用強度 0.050
- `replayed_commands.csv` と `adapter_status.csv` の両方に `direction` が記録される

**camera-side synthetic track（G923なし）**
- `bird_eye.update_steering_gradient()` → `publish_collision_ffb()`
  → 実 `CollisionFfbPublisherBridge` → dry-run node
- 左トラック: `raw=+0.649`、`filtered=+0.646`、`direction=-1`
- 右トラック: `raw=-0.649`、`filtered=-0.646`、`direction=+1`
- node は `applied=0.050`、fault 0、close 時 `direction=0`

実カメラ動画での dry-run は、利用可能な録画に
「移動する360映像＋有効なブルートラック」がなかったため未実施。
`bird_eye` の勾配計算・publisher 接続自体は上記の合成トラックで確認済み。

**残り**
- 実カメラ/実トラックでの dry-run
- `collision_ffb_direction_enabled=1` で `gradient_*` が status / log / CSV に残ることの実環境確認
- watchdog 100 ms、期限切れ、重複・逆順で STOP（単体テスト済み）

### 8.3 ハードウェア（未実施、停止状態）
- 0.03 以下で左右の向きを確認
- `constant_direction_sign` の符号を確定
- 0.05 で「重い／軽い」の差が知覚できるか
- 異常時（Ctrl+C、USB切断）に力が残らない

---

## 9. 実験計画（論文用）

### 9.1 条件（被験者内）
1. FFBなし
2. 大きさのみ（`ĝ=0`）
3. 大きさ＋勾配（`direction` あり）

順序はランダム化、条件間に練習試行、同一コース・同一障害物配置。

### 9.2 指標
- 危険方向への操作率（**主要指標**）
- 回避開始までの時間
- 最小クリアランス / 接触率
- ω反転回数、jerk
- NASA-TLX（負荷。「喧嘩」していないかの確認）

### 9.3 仮説
- H1: 勾配ありは危険方向への操作率が下がる
- H2: 勾配ありは最小クリアランスが増える
- H3: 勾配ありでもNASA-TLXは悪化しない（抵抗型の利点）

### 9.4 必要人数の目安
- 予備実験: 3名（操舵の理解、トルク調整）
- 本実験: 10名前後（被験者内、効果量を見て追加）
- 倫理審査・同意取得の要否を所属で確認

---

## 10. 未決事項

- `Δ` と `k` の初期値（予備実験で決定）
- `G_SCALE` の正規化方法（TTC基準かリスク基準か）
- `path_eta_sec` を TTC 代理とする簡易版で十分か、厳密な経路TTCに置き換えるか
- 複数障害物時のリスク統合（max か sum か）
- 4輪との差を示す比較方法（実機4輪は不要。シミュレーションで入力勾配と空間勾配のズレを示す案）
- `constant_direction_sign` の最終値（実機で左右方向を確認して決定）
- 実機で `FF_CONSTANT` の知覚強度が periodic とどう違うか（同じ `max_magnitude` で比較）

### 決定済み

- 指令には `direction`（-1/0/+1）を載せる。`ĝ` はカメラ側の記録に残す。
  - 受信側が単純で、既存の `normalized_magnitude` 検証を壊さないため。
- 方向出力は `direction_enabled=true` の hardware モードでのみ有効にする。
- 後退時は勾配の符号と左右ラベルを反転する。
- 非アクティブと PULSE は `direction=0` を必須とする。

---

## 11. 適用時の注意

- 新旧メッセージを混在させない（両PCで `oit_interfaces` を再ビルド）
- 最初は `output_mode=dry_run` で `direction` の伝搬だけ確認
  - dry-run では `direction_enabled=false` のままでも direction が status / 記録に出る
- ハードウェアは停止状態・短時間・低強度から
- 方向出力を有効にするときだけ `direction_enabled=true` にする
- 既存の `hardware_armed` / `challenge_hardware_armed` を省略しない
- 実機で左右が逆なら `constant_direction_sign=-1` にする
- `direction_enabled=true` の hardware モードでは `FF_CONSTANT` 非対応デバイスを起動時に拒否する
