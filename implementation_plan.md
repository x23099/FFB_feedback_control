# TTC連動G923 Force Feedback 実施計画書

作成日: 2026-09-08
対象リポジトリ:

- `/home/robo25/FFB_feedback_control/FFB_feedback_control`
- `/home/robo25/theta_ws/RICHO-theta`

## 1. 目的

`RICHO-theta`で算出済みの衝突リスク状態をROS 2で送信し、Logitech G923へ安全制限付きの
Force Feedback（FFB）として提示する。

最初の到達点は、青箱に対するTTC `WARNING` / `WARNING_HOLD`を、Kobukiを走行させない状態で
G923の弱い振動として確認することである。YOLOによる一般物体認識、自動停止、Kobuki速度指令の変更は
この実施計画の対象外とする。

## 2. 現状と確認済み事項

### 2.1 認識・TTC側

- `RICHO-theta/src/virtual_ffb.py`で衝突状態からデバイス非依存の要求へ変換できる。
- 現行の正規化要求は`CLEAR/PATH=0.00`、`UNKNOWN=0.15`、`WARNING/WARNING_HOLD=0.25`、
  `CRITICAL=0.40`である。
- 2026-09-08 TTC v6 holdoutは、正式3試行すべてで確認可能な警告機会に対してWARNINGが成立した。
- r02の生検出率未達は至近距離の下端輪郭欠落であり、TTC警告動作そのものは3試行すべてで確認できた。
- この結果を実用上の次段階移行条件として採用し、同条件の追加録画は必須としない。

### 2.2 G923側

- USB ID: `046d:c266`
- 製品名: `Logitech G923 Racing Wheel for PlayStation 4 and PC`
- 安定デバイスパス:
  `/dev/input/by-id/usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_USYMUGUXEREJOFORUFUMEZIDU-event-joystick`
- 実体: `/dev/input/event22`（番号は再接続で変化し得るため、実装では安定パスを使う）
- `hsr`は`input`グループ所属で、デバイスは読み書き可能。
- 保持可能effect数: 16
- `FF_PERIODIC`、`FF_SINE`、`FF_SQUARE`、`FF_SPRING`、`FF_CONSTANT`、`FF_RUMBLE`、
  `FF_GAIN`、`FF_AUTOCENTER`などに対応する。

### 2.3 既存FFB実装

`FFB_feedback_control/src/oit/oit/ffb_follow.py`には次が実装済みである。

- Python `evdev`によるG923のオープン、effect upload、再生、停止、削除
- `FF_SPRING`による車体旋回追従
- `FF_PERIODIC`による緊急停止・段差・通信断通知
- ROS 2 parameter、topic、終了時クリーンアップ

ただし、現在の実装は起動時にAutocenterを変更し、タイマーからSpringを物理再生する。また、
通信断時はゼロ出力ではなく強いセンタリングロックを行う。TTC要求用の明示的enable、dry-run、
100 ms watchdog、意味付き入力topicはない。そのため、既存launchをTTC試験へ直接使用しない。

## 3. 設計原則

1. **fail closed**: 不正値、古い要求、通信断、例外では新しい力を出さず、実行中effectを停止する。
2. **物理出力は既定無効**: 明示的にhardwareモードを指定しない限りデバイスへ書き込まない。
3. **有限時間effect**: プロセス停止やハング時にも力が残りにくいよう、effect自体の再生時間を有限にする。
4. **強度を二重制限**: 受信値を`0..1`へ検証し、設定上限とコード上の絶対上限の両方で制限する。
5. **単一writer**: G923へFFBを書き込むプロセスを同時に複数起動しない。
6. **車体制御と分離**: FFB異常によって`/cmd_vel`やKobuki速度指令を変更しない。
7. **段階導入**: 単体テスト、dry-run、合成要求、録画再生、停止状態の実機試験、ライブ接続の順を守る。

Linux Kernel仕様では、effectはuploadしただけでは再生されず、`EV_FF` eventによって再生・停止する。
また初期化時に機器が予期せず強く動く可能性が明記されている。FFB gainはデバイスに残る可能性があるため、
初期実装ではグローバル`FF_GAIN`を変更せず、個別effectのmagnitudeだけを制限する。

## 4. 採用アーキテクチャ

```text
RICHO-theta / bird_eye.py
  collision_risk_level
        │
        ├─ VirtualFfbPolicy（状態→正規化要求）
        │
        └─ /collision/ffb_command  約30 Hz、KeepLast(1)
                    │
                    ▼
FFB_feedback_control / collision_ffb_node
  schema・sequence・時刻・値域検証
        │
        ├─ disabled: 出力せず状態だけ記録
        ├─ dry_run: effect操作予定をログ・statusへ出力
        └─ hardware: 上限付き有限FF_PERIODICをG923へ出力
                    │
                    ▼
Logitech G923 event-joystick
```

初期版は既存の旋回追従`ffb_follow_node`とは別ノードにする。既存コードへ直接追加すると、
起動時Springや通信断ロックとTTC警告の原因切り分けが難しくなるためである。

`handle.py`による入力読み取りとの同時使用は許容する。一方、`ffb_follow_node`、`spring_test.py`、
`periodic_test.py`など、G923へFFBを書き込む別プロセスとの同時使用は禁止する。

## 5. ROS 2インターフェース

### 5.1 メッセージ

意味と時刻を持たない`std_msgs/Float32`単独にはせず、独立interface packageへ次を定義する。

`oit_interfaces/msg/CollisionFfbCommand.msg`:

```text
std_msgs/Header header
uint64 sequence
string source

uint8 CLEAR=0
uint8 PATH=1
uint8 WARNING=2
uint8 WARNING_HOLD=3
uint8 CRITICAL=4
uint8 UNKNOWN=5
uint8 risk_level

uint8 OFF=0
uint8 STEADY=1
uint8 STEADY_HOLD=2
uint8 PULSE=3
uint8 pattern

bool active
float32 normalized_magnitude
string reason
```

topic名は`/collision/ffb_command`とする。`header.stamp`は生成時刻、`sequence`は起動中単調増加、
`source`は初期版では`bird_eye`とする。

### 5.2 QoSと鮮度

- History: `KEEP_LAST`
- Depth: 1
- Reliability: `BEST_EFFORT`
- Durability: `VOLATILE`
- publish周期: カメラ処理ごと、目標約30 Hz
- adapter watchdog: 最後に妥当な要求を受信してから100 ms
- ROS時刻は診断へ使用し、実際のwatchdog判定は時刻ジャンプの影響を避けるためmonotonic clockを使用する。

QoSだけへ安全停止を依存させない。Lifespanを利用できる構成でも、adapter自身のwatchdogを必須とする。

### 5.3 無効要求の扱い

- `active=false`または`CLEAR/PATH`: 即時停止
- 有効な`UNKNOWN`: 弱いpulse要求として扱う
- schema不整合、NaN/Inf、範囲外、古いsequence、古いstamp、未知enum: 出力停止・fault記録
- topic停止、publisher停止、100 ms超過: 出力停止・`watchdog_timeout`記録

認識結果としての`UNKNOWN`と、通信・メッセージ異常を区別する。後者をUNKNOWN振動へ変換しない。

## 6. G923物理出力方式

### 6.1 初期effect

- 種別: `FF_PERIODIC`
- 波形: `FF_SINE`を第一候補とする。既存のSquareより立ち上がりが滑らかなため、最小強度試験に向く。
- 方向: 既存実装と同じ`16384`を初期値とし、停止状態で左右方向を確認する。
- 1回の再生時間: 最大100～120 ms
- active要求継続中のみ50 ms程度で再トリガーする。
- inactive、watchdog、例外、終了では`EV_FF value=0`後にeffectをeraseする。

再生時間自体を有限にすることで、adapterのタイマーが停止しても力が長時間残らない構成とする。

### 6.2 強度制限

- 受信値: `0.0 <= normalized_magnitude <= 1.0`のみ受理
- コード上の絶対上限: 初期版0.25
- 設定上限: 既定0.05
- 初回物理試験: 0.03以下
- G923へ送る値: `round(32767 * min(request, configured_cap, absolute_cap))`

正規化値は物理トルクを表さない。体感確認後も、絶対上限を引き上げる場合は別変更・別承認とする。

### 6.3 出力モード

ROS parameter `output_mode`を次の3値に限定する。

| mode | デバイスopen | upload/write | 用途 |
|---|---:|---:|---|
| `disabled` | しない | しない | 既定値・通常開発 |
| `dry_run` | しない | しない | 状態遷移とwatchdog検証 |
| `hardware` | する | する | 明示承認後の停止状態試験 |

未知のmodeは起動エラーとする。実行中にservice等で`hardware`へ切り替える機能は初期版では作らず、
物理出力には明示的な再起動を必要とさせる。

## 7. 単一writer対策

G923のeffectはファイルディスクリプタごとに所有される一方、AutocenterやGainは他プロセスと干渉し得る。
次を実装する。

1. device pathから一意なlock名を作り、`/run/user/<uid>/`で排他lockを取得する。
2. `collision_ffb_node`はhardwareモードでlockを取得できなければ起動失敗する。
3. 既存`ffb_follow.py`と物理テストスクリプトにも同じlock helperを適用する。
4. `handle.py`は入力readerなので、このFFB writer lockの対象外とする。
5. 初回実機試験前に`/ffb_follow_node`が存在しないことも運用確認する。

## 8. 実装対象

### 8.1 `FFB_feedback_control`

新規候補:

- `src/oit_interfaces/CMakeLists.txt`
- `src/oit_interfaces/package.xml`
- `src/oit_interfaces/msg/CollisionFfbCommand.msg`
- `src/oit/oit/collision_ffb_policy.py`: 入力検証、状態遷移、clamp、watchdog判定
- `src/oit/oit/collision_ffb_device.py`: evdev backend、effect生成、停止、排他lock
- `src/oit/oit/collision_ffb_node.py`: ROS subscriber、timer、診断publish
- `src/oit/config/collision_ffb.yaml`: 既定disabled、100 ms watchdog、強度上限
- `src/oit/launch/collision_ffb_dry_run.launch.py`
- `src/oit/test/test_collision_ffb_policy.py`
- `src/oit/test/test_collision_ffb_device.py`

更新候補:

- `src/oit/setup.py`: console script、設定・launch登録
- `src/oit/package.xml`: 実際のruntime依存関係を追加
- `src/oit/oit/ffb_follow.py`: 共通writer lockだけを適用
- `src/oit/oit/spring_test.py`、`periodic_test.py`: 共通writer lockと明確な物理出力警告
- `README.md`: 安全な起動順、禁止する同時起動、停止方法

既存のSpring計算、旋回追従、段差、緊急停止、Kobuki速度制御の挙動は変更しない。

### 8.2 `RICHO-theta`

新規候補:

- `src/collision_ffb_publisher.py`: `VirtualFfbCommand`からROS messageへの変換
- `tests/test_collision_ffb_publisher.py`: enum対応、sequence、値域、時刻

更新候補:

- `src/bird_eye.py`: 衝突状態決定後に最新要求をpublish
- `src/preflight_field_experiment.py`: interface importとtopic設定の検査
- TTC v6用config: publisher enable/topicを明示。ただしFFB publisherの既定値は無効とする。
- 録画metadata/CSV: FFB command sequence、active、magnitude、pattern、publish結果を記録

`virtual_ffb.py`の純粋ポリシーを共通利用し、ライブとオフラインで状態から要求への変換規則を二重実装しない。

## 9. 実装手順と完了条件

### Phase 1: interface・純粋ロジック

1. `CollisionFfbCommand.msg`を追加する。
2. 入力検証、強度clamp、sequence検査、watchdog状態機械をデバイス非依存で実装する。
3. fake clockとfake backendで単体テストする。

完了条件:

- hardware importやROS実行環境がなくても純粋ロジックのテストがPASSする。
- NaN/Inf、範囲外、未知enum、古いsequenceをすべてfail closedにできる。
- 100 ms経過時に1回だけstop要求が出る。

実施結果（2026-09-08）:

- `oit_interfaces/msg/CollisionFfbCommand.msg`とinterface packageを追加した。
- ROS・evdev非依存の`CollisionFfbSafetyPolicy`を追加し、時刻はテストから注入できる構成にした。
- hardware backendへ接続せず、抽象`APPLY/STOP/NONE`までを32件の単体テストで検証した。
- NaN/Inf、範囲外、未知enum、不正なstate/pattern、古いstamp、古いsequenceをfail closedにした。
- 100 ms watchdogの一回限りのSTOP、強度の設定上限・絶対上限clampを確認した。
- 新規Pythonファイルのflake8/pydocstyle、interface生成、ROS 2 package buildがPASSした。
- Phase 1完了。Phase 2および物理FFB出力には未着手である。

### Phase 2: dry-run ROS adapter

1. `collision_ffb_node`を`disabled` / `dry_run`で起動できるようにする。
2. 合成messageで`CLEAR→WARNING→HOLD→CLEAR`を再生する。
3. publisherを停止し、100 ms watchdogを確認する。
4. status topicとログへ、受信sequence、要求値、clamp後値、停止理由を出す。

完了条件:

- dry-run時に`InputDevice`、`upload_effect`、`write`を一度も呼ばない。
- 例外、Ctrl+C、topic停止で最終状態が`inactive`になる。
- 全テストと既存ROS packageのbuild/testがPASSする。

実施結果（2026-09-09）:

- `CollisionFfbStatus.msg`を追加し、sequence、受信強度、clamp後強度、pattern、停止理由、faultを構造化した。
- `collision_ffb_node`を追加し、既定`disabled`と明示`dry_run`だけを実装した。
- Phase 2ノードは`evdev`をimportせず、`InputDevice`、`upload_effect`、device writeを持たない構成にした。
- `output_mode=hardware`はデバイスへ接触する前に起動エラーとなることを実行確認した。
- 合成ROS 2指令で`CLEAR→WARNING→WARNING_HOLD→CLEAR`を再生し、状態列を確認した。
- 受信強度0.25が既定上限0.05へclampされることを、statusと実行ログの両方で確認した。
- active指令を最後にpublisherを停止し、約104 ms後に`watchdog_timeout`のSTOPが1回発生した。
- launchをCtrl+Cで終了したとき、`reason=shutdown`のinactive statusを出して正常終了した。
- 安全ポリシーとROS adapterの対象テストは43件すべてPASSし、2 packageのROS 2 Humble buildもPASSした。
- 既存ファイルを含むリポジトリ全体のlintには従来の警告が残るが、Phase 1・2の新規ファイルは
  flake8/pydocstyleに合格した。
- Phase 2完了。Phase 3、evdev backend、G923物理出力には未着手である。

### Phase 3: `RICHO-theta`ライブpublisher

1. `bird_eye.py`の確定済みリスク状態を約30 Hzでpublishする。
2. v6 configでpublisherを有効化し、adapterはdry-runのまま接続する。
3. 2026-09-08録画または合成入力を用いて、仮想FFBとdry-run状態列を比較する。

完了条件:

- `CLEAR/PATH`では出力要求0。
- `WARNING/WARNING_HOLD`で0.25の要求が生成される。
- adapter側では既定cap 0.05へ制限される。
- 録画再生時のactive区間・イベント数が既存`virtual_ffb_replay.csv`と一致する。
- カメラ処理停止後100 msでadapterがinactiveになる。

実施結果（2026-09-09）:

- `RICHO-theta/src/collision_ffb_publisher.py`を追加し、既存`VirtualFfbPolicy`を
  ライブ側でも共通利用した。
- `bird_eye.py`のヒステリシス適用後リスクを処理フレームごとにpublishし、終了時は
  `CLEAR`を送ってからnodeを破棄するようにした。
- publisherは既定無効を維持し、v6設定からFFB項目だけを追加した
  `bird_eye_config_ttc_v6_ffb_dry_run_20260909.json`で明示的に有効化した。
- preflightへtopic、source、強度順序、`oit_interfaces.msg`の検査を追加した。
- 録画metadataとCSVへpublisher設定、sequence、active、要求強度、pattern、送信成否、
  エラーを保存するようにした。
- `RICHO-theta`の全159テストと、FFB用ROS環境をsourceしたpreflightがPASSした。
- 2026-09-08録画`202609081640.tar.xz`の4セッション計2,502フレームをv6 profileで
  再生し、activeフレーム数、リスク別フレーム数、event数、peak強度が既存CSVと一致した。
- 実ROS 2通信で`CLEAR/PATH=0.00`、`WARNING/WARNING_HOLD=0.25`、
  `CRITICAL=0.40`を確認し、adapter側ではactive要求がすべて0.05へ制限された。
- 30.0 Hzで30 commandを送受信し、publisher停止後約100 msで
  `watchdog_timeout`のinactive状態へ遷移した。終了時も`shutdown`のinactiveを確認した。
- G923へのアクセスと物理FFB出力は行っていない。
- Phase 3完了。Phase 4は未承認・未着手である。

### Phase 4: 停止状態の最小物理出力

次の全条件を満たした場合だけ実施する。

1. G923を机へ固定し、周囲から手、物、ケーブルを退避する。
2. Kobukiの速度出力を無効にし、車体を走行させない。
3. `ffb_follow_node`、`spring_test`、`periodic_test`が停止している。
4. すぐにG923のUSBまたは電源を切れる。
5. まず合成要求を使用し、カメラ・TTCとは接続しない。
6. `output_mode=hardware`、設定上限0.03、1イベントだけで開始する。

試験順:

1. 起動しただけでは無出力であることを確認する。
2. 0.03のWARNINGを0.5秒以内だけ送る。
3. CLEARで直ちに停止することを確認する。
4. publisher停止後100 msと、Ctrl+C後の停止を確認する。
5. 必要な場合のみ0.05まで段階的に上げる。

完了条件:

- 予定外のAutocenter変更・Spring移動がない。
- WARNING振動を知覚できる。
- CLEAR、watchdog、Ctrl+Cの全経路で力が停止する。
- effect IDがeraseされ、再起動時にslotが減少しない。
- 異音、急回転、発熱、通信不安定がない。

異常が一つでもあればUSB/電源を切り、hardware試験を中止する。

### Phase 5: TTC連動の停止状態試験

1. Kobukiを動かさず、青箱または録画再生でTTC状態を生成する。
2. `bird_eye.py` → ROS topic → adapter → G923の全経路を確認する。
3. FFB状態、入力sequence、watchdog、処理時刻を記録する。

完了条件:

- WARNING開始からG923出力要求までのソフトウェア遅延p95が100 ms以内。
- CLEAR/PATH、アプリ終了、カメラ停止でFFBが残らない。
- 仮想FFBログと物理adapterログの状態遷移が一致する。

走行しながらのTTC連動試験は、この計画完了後に別計画として扱う。

## 10. 必須テスト

| 分類 | テスト内容 |
|---|---|
| 値検証 | NaN、Inf、負値、1超過、未知enumを拒否 |
| 状態 | CLEAR/PATHで停止、WARNING/HOLDでactive、UNKNOWNは有効な弱pulse |
| 鮮度 | 100 ms超過、古いsequence、古いstampで停止 |
| 上限 | 要求0.25が設定cap 0.05を超えない |
| 起動 | 既定disabledでデバイスをopenしない |
| dry-run | evdevへの書込み0回 |
| capability | `FF_PERIODIC`非対応またはeffect slot不足でhardware起動失敗 |
| 排他 | 2つ目のwriterが起動失敗 |
| 例外 | upload/write失敗後にstop/closeを試行し、faultを記録 |
| 終了 | CLEAR、watchdog、Ctrl+Cで停止・erase |
| 回帰 | 既存`virtual_ffb.py`、TTC、録画解析、handle関連テストを壊さない |

物理effectはmock/fake backendで検証し、通常の自動テストから実機へ書き込まない。実機試験は明示的な
手動手順だけとする。

## 11. 依存関係とビルド

- ROS 2 Humbleを対象とする。
- `python3-evdev`または固定したPython `evdev`版をruntime依存として明記する。
- `rosidl_default_generators`等、interface packageに必要な依存を明記する。
- `ffset`はTTC adapterでは使用しない。既存`ffb_follow.py`で必要な外部コマンドとしてREADMEへ明記する。
- `colcon build --packages-select oit_interfaces oit`と`colcon test`を実施する。
- `RICHO-theta`側の既存Python単体テストもすべて実施する。

Python-evdev 2.0以降にはread-only open指定があるが、学校PCの導入版を確認してから使用可否を決める。
hardware adapterは書込みが必要なため、read-only指定へ依存しない。

## 12. リスクと対策

| リスク | 対策 |
|---|---|
| 起動直後の予期しない力 | 既定disabled、hardware時も初回要求までupload/playしない |
| プロセス停止後に力が残る | 100～120 ms有限effect、watchdog、終了時stop/erase |
| 過大な力 | 初回cap 0.03、既定0.05、コード絶対上限0.25 |
| 古いDDS要求の再生 | KeepLast(1)、Volatile、sequence/stamp検証、monotonic watchdog |
| 複数writer干渉 | 共通lock、既存FFBノード停止確認 |
| Autocenter/Gainの残留 | TTC adapterでは両方を変更しない |
| TTCアプリ停止 | 100 msでinactive、有限effectで自己停止 |
| デバイス抜去 | 例外をfault化し、再接続を自動実行せず明示再起動 |
| FFB異常で車体が動く | adapterは速度topicをpublishしない、Kobuki停止状態で試験 |
| 既存旋回FFBの破壊 | 初期版は独立ノード、既存計算を変更しない |

## 13. ロールバック

- 新規adapterは既存launchへ自動追加しないため、起動しなければ従来挙動へ影響しない。
- 異常時はCtrl+C、G923 USB/電源切断の順で停止する。
- コード上は新規ノードとinterfaceを外せば、既存`ffb_follow.py`と`handle.py`へ戻せる。
- `bird_eye.py`のpublisherは既定無効とし、FFB未導入環境でも従来通り動作させる。
- TTC閾値、観測ゲート、Kobuki速度制御の設定は本作業で変更しない。

## 14. 成果物

1. 意味付き`CollisionFfbCommand` message
2. disabled/dry-run/hardware対応adapter
3. 100 ms watchdogと有限時間effect
4. 強度上限・排他lock・終了時停止
5. `bird_eye.py`の任意有効publisher
6. mockによる単体テストと回帰テスト
7. dry-run結果、停止状態実機試験結果、実行ログ
8. README、起動・停止・異常時手順
9. 両リポジトリの日報・commit

## 15. 実装を開始しない条件

次のいずれかに該当する場合、物理出力実装または実機試験へ進まない。

- 本計画書へのユーザー承認がない。
- 既存FFB writerとの排他方法が実装されていない。
- disabled/dry-run、watchdog、有限effect、強度上限、終了時停止のテストが未完了。
- G923の固定、周囲安全、即時電源断手段を確保できない。
- Kobukiの走行出力を確実に無効化できない。

## 16. 根拠資料

- Linux Kernel Force Feedback仕様: <https://www.kernel.org/doc/html/latest/input/ff.html>
- Python-evdev API: <https://python-evdev.readthedocs.io/en/latest/apidoc.html>
- ROS 2 topic/interfaceの使い分け: <https://docs.ros.org/en/jazzy/How-To-Guides/Topics-Services-Actions.html>
- ROS 2 Humble QoS: <https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html>
- 既存仮想FFB設計: `/home/robo25/theta_ws/RICHO-theta/Experimental_results/2026-09-03/2026-09-03_virtual_ffb_design.md`

## 17. 承認

- ユーザー確認: 2026-09-08承認済み
- 実装開始: Phase 1・2許可済み・完了
- 物理FFB試験: 実装・dry-run完了後に別途確認

本計画書の承認後はPhase 1から着手し、Phase 3までをソフトウェア作業として進める。Phase 4の物理出力は、
ソフトウェア安全ゲートの結果を提示した後、改めてユーザーの明示確認を得てから実施する。
