# FFB_feedback_control

## 概要

本システムは、Logitech G923(以下ハンコン)を使用してAIformula実機を遠隔操作し、自律走行中には実機の旋回挙動をフォースフィードバックとしてハンドルへ反映するシステムである。

主に次の3つの機能を持つ。

1. G923によるAIformula実機の手動操作
2. 自律走行中の手動オーバーライド
3. AIformulaの旋回挙動をハンコンへ反映するFFB制御

ハンコンを接続するPCでは、主に次の2つのノードを動作させる。

* `handle.py`
* `ffb_follow.py`

AIformula実機側では、既存の`twist_mux`、自律走行ノード、オドメトリ発行ノードなどを使用する。

---

# aiformula_launch.py

## 役割

`aiformula_launch.py`は、AIformula用のノードと設定をまとめて起動するLaunchファイルである。

主な役割は次のとおり。

* `handle.py`の起動
* `ffb_follow.py`の起動
* `handle.py`の出力トピックのremap
* `ffb_follow_aiformula.yaml`の読み込み
* AIformula用トピックへの接続

起動コマンドは次のとおり。

```bash
ros2 launch oit aiformula_launch.py
```

このコマンドにより、ハンコンの入力処理とFFB制御をまとめて開始できる。

---

## handle.pyの起動とremap

`handle.py`は本来、操作指令を

```text
/cmd_vel_joy
```
へpublishする。

AIformula側では、ハンコンの操作指令を

```text
/aiformula_control/handle_controller/cmd_vel
```
で受け取る。

そのため、Launchファイル内でremapを行う。

このremapにより、`handle.py`のプログラム本体を書き換えずに、AIformula用のトピックへ操作指令を送ることができる。

これは、次のコマンドで単体起動した場合と同じremapである。

```bash
ros2 run oit handle \
  --ros-args \
  -r /cmd_vel_joy:=/aiformula_control/handle_controller/cmd_vel
```

---

## ffb_follow.pyの起動

AIformula用設定ファイルであるffb_follow_aiformula.yamlを取得する。
取得した設定ファイルを`ffb_follow_node`へ渡す。
これにより、`ffb_follow.py`はAIformula用のトピック名やFFB設定を使用して動作する。

---

# ffb_follow_aiformula.yaml

## 役割

`ffb_follow_aiformula.yaml`は、AIformula用のFFB設定ファイルである。

主に次の情報を設定する。

* `ffb_follow.py`が購読するトピック
* G923のデバイスパス
* Autocenterの強さ
* Springエフェクトの強さ
* 車体のyaw角からハンドル角への変換倍率
* 自律旋回と判定する閾値
* FFB中心位置の更新速度

---

# FFBの仕組み

## Linux Force Feedback

G923のFFB制御には、Linuxの入力サブシステムが提供するForce Feedback機能を使用する。

Force Feedbackでは、ハンドルへ与える力を「エフェクト」としてデバイスへ登録する。

代表的なエフェクトには次のようなものがある。

* `FF_CONSTANT`
* `FF_PERIODIC`
* `FF_SPRING`
* `FF_DAMPER`
* `FF_FRICTION`
* `FF_RUMBLE`

本システムでは、主に`FF_SPRING`を使用する。

---

## FF_SPRING

`FF_SPRING`は、指定した中心位置へハンドルを戻そうとする力を発生させるエフェクトである。

通常のハンドルでは中心位置は0である。

```text
左端         中央         右端
-32768        0          32767
```

中心位置を右方向へずらすと、ハンドルは右側の位置へ引っ張られる。

---

## FF_SPRINGの主な設定値

### center

ハンドルを戻そうとする目標中心位置。

### coefficient

中心位置からずれたときに発生する力の強さ。

yamlでは次のように設定する。

```yaml
auto_spring_coeff: 18688
manual_spring_coeff: 18688
idle_spring_coeff: 12288
```

### saturation

発生する力の最大値。

```yaml
auto_spring_saturation: 24576
manual_spring_saturation: 24576
idle_spring_saturation: 18432
```

---

# 実機の旋回をハンコンへ反映する処理

## 1. 旋回開始の検出

`ffb_follow.py`は、次のトピックを監視する。

```text
/aiformula_control/twist_mux/cmd_vel
```

この中の`angular.z`が閾値を超えると、旋回開始と判断する。

```text
abs(angular.z) > auto_angular_threshold
```

旋回開始時点のyaw角を保存する。

```text
start_yaw = 現在のyaw角
```

---

## 2. yaw角の変化量を計算

旋回中はオドメトリから現在のyaw角を取得する。

```text
yaw_delta = current_yaw - start_yaw
```

角度が`-180度`から`180度`の境界をまたぐ場合があるため、実際のプログラムでは角度の正規化を行う。

```text
例

旋回開始時: 170度
現在角度  : -170度

単純な差分: -340度
実際の旋回: 20度
```

正規化処理により、正しい旋回量を求める。

---

## 3. yaw角からハンドル角へ変換

車体のyaw変化量をハンコンの目標角度へ変換する。

基本式は次のとおり。

```text
target_handle_deg
=
yaw_delta_deg
×
yaw_to_handle_ratio
```

---

## 4. ハンドル角からcenter値へ変換

G923のハンドル角度範囲は、中央から左右それぞれ約450度である。

```text
左限界: -450度
中央  : 0度
右限界: +450度
```

Force Feedback内部では、中心位置を概ね次の範囲で扱う。

```text
-32768 ～ 32767
```

そのため、目標ハンドル角を次のように変換する。

```text
center
=
target_handle_deg
÷
handle_limit_deg
×
32768
```

この`center`値を`FF_SPRING`の中心位置として設定する。

実際のプログラムでは、ハンドルの限界を超えないように値を制限する。

```text
-32768 <= center <= 32767
```

---

## 5. center値を徐々に更新

目標位置を一度に大きく変更すると、G923が急激に回転する可能性がある。

そのため、現在値から目標値へ少しずつ近づける。

```yaml
max_center_step: 400
```

概念的には次の処理になる。

```text
目標center: 8000
現在center: 2000
1回の最大変化量: 400

次のcenter: 2400
```

これを一定周期で繰り返す。

```yaml
spring_update_period: 0.05
```

`0.05秒`は、約20 Hzでの更新を意味する。

---

# FFBの動作モード

`ffb_follow.py`には、主に次の3つの動作モードがある。

## 待機モード

次の条件で使用する。

```text
手動操作をしていない
かつ
旋回指令が出ていない
```

弱い力でハンドルを中央付近へ保持する。

---

## 自律旋回モード

次の条件で使用する。

```text
manual_active = False
かつ
abs(angular.z) > auto_angular_threshold
```

通常のAutocenterを無効にし、`FF_SPRING`の中心位置を車体のyaw変化に合わせて移動する。

```text
AIformulaが右旋回
    ↓
yaw角が変化
    ↓
FF_SPRINGのcenter値を更新
    ↓
ハンコンが右方向へ移動
```

---

## 手動操作モード

次の条件で使用する。

```text
manual_active = True
```

自律追従を停止し、手動操作向けの中央復帰力へ切り替える。

これにより、自律走行中にハンコンを操作しても、自律制御によってハンドルが引っ張られ続けることを防ぐ。

---

# 手動オーバーライド

自律走行中にハンコン操作を開始すると、実機操作側とFFB側で2つの処理が同時に行われる。

## 1. 実機操作側

`handle.py`が手動速度指令をpublishする。

```text
handle.py
    ↓
/aiformula_control/handle_controller/cmd_vel
    ↓
AIformula側 twist_mux
    ↓
手動指令が自律指令より優先される
    ↓
AIformulaが手動操作へ切り替わる
```

AIformula側の`twist_mux`が優先順位に基づいて手動指令を選択するため、自律走行中でも人間の操作で上書きできる。

---

## 2. FFB側

同時に、`handle.py`が

```text
/handle/manual_active
```
をpublishする。手動操作中は

```yaml
data: true
```
となり、`ffb_follow.py`はこれを検知すると、自律走行へのハンドル追従を停止する。

```text
manual_active = True
    ↓
自律追従モードを停止
    ↓
FF_SPRINGの中心を中央へ戻す
    ↓
手動操作用の反力へ変更
```

これにより、手動操作中は運転者自身がハンドルを操作できる。

---

# 手動操作終了後の復帰

手動操作を終了すると、`handle.py`が

```yaml
data: false
```
になり、AIformula側の`twist_mux`では、手動速度指令が一定時間届かなくなると、手動入力がタイムアウトする。

```text
手動指令が停止
    ↓
twist_muxのtimeout
    ↓
自律走行指令が再び選択される
```

`ffb_follow.py`側では、`manual_active`が`False`になった後、最終速度指令とオドメトリを確認し、自律走行状態に応じたFFB制御へ戻る。

AIformula側の`twist_mux`のタイムアウトと、`ffb_follow.py`の状態更新は別々の処理である。

---

## 購読トピック一覧

### auto_cmd_topic

```text
/aiformula_control/twist_mux/cmd_vel
```

AIformula側の`twist_mux`が選択した、最終的な速度指令である。

メッセージ型は

```text
geometry_msgs/msg/Twist
```
であり、主に次の値を使用する。

```text
linear.x
angular.z
```

* `linear.x`: 前進・後退速度
* `angular.z`: 旋回速度

`ffb_follow.py`は、主に`angular.z`を確認して、実機が旋回中かどうかを判断する。

設定した閾値より大きい場合、自律旋回中として扱う。

---

### odom_topic

```text
/aiformula_sensing/gyro_odometry_publisher/odom
```

AIformulaの位置と向きを取得するトピックである。

メッセージ型は

```text
nav_msgs/msg/Odometry
```
であり、`ffb_follow.py`は、オドメトリ内のQuaternionから車体のyaw角を計算する。

yaw角は、車体が水平方向にどちらを向いているかを表す。

```text
Quaternion
    ↓
yaw角
    ↓
旋回開始時からの角度変化量
```

この角度変化量を、ハンコンの目標角度へ変換する。

---

### manual_active_topic

```text
/handle/manual_active
```

人間が手動介入しているかを表すトピックである。

メッセージ型は

```text
std_msgs/msg/Bool
```
であり、値の意味は

```text
False
人間が操作していない

True
人間が手動操作している
```
である。このトピックは、このPCで動作する`handle.py`がpublishする。

`ffb_follow.py`はこの値を使用して、自律追従モードと手動操作モードを切り替える。

---

# handle.py

## 役割

`handle.py`は、ハンコンから入力データを取得し、ROS2の速度指令へ変換する。

主に取得する情報は

* ハンドル角度
* アクセル
* ブレーキ
* クラッチ
* ギア
* 各種ボタン
であり、これらの入力から、`geometry_msgs/msg/Twist`形式の操作指令を作成する。

# AIformula側のtwist_mux

## 役割

AIformula側の`twist_mux`は、複数の速度指令から、優先度の高い指令を選択する。

主な入力は次の2つである。

### 自律走行指令

```text
/aiformula_control/twist_mux/cmd_vel
```

### 手動操作指令

```text
/aiformula_control/handle_controller/cmd_vel
```

ハンコンを接続しているPCの`handle.py`から送られる手動操作指令である。

---

## 最終出力

AIformula側の`twist_mux`が選択した指令は、次のトピックへ出力される。

```text
/aiformula_control/twist_mux/cmd_vel
```

このトピックは、現在実機へ適用されている最終的な速度指令を表す。

```text
通常時
自律走行指令が選択される

ハンコン操作時
手動操作指令が選択される
```

`ffb_follow.py`もこの最終出力を監視する。

# 主なROS 2トピック

| トピック                                              | メッセージ型                    | 発行元                   | 購読先                   | 内容          |
| ------------------------------------------------- | ------------------------- | --------------------- | --------------------- | ----------- |
| `/aiformula_control/handle_controller/cmd_vel`    | `geometry_msgs/msg/Twist` | `handle.py`           | AIformula側`twist_mux` | ハンコンの手動速度指令 |
| `/handle/manual_active`                           | `std_msgs/msg/Bool`       | `handle.py`           | `ffb_follow.py`       | 手動介入状態      |
| `/aiformula_control/lane_line_controller/cmd_vel` | `geometry_msgs/msg/Twist` | 自律制御ノード               | AIformula側`twist_mux` | 自律走行指令      |
| `/aiformula_control/twist_mux/cmd_vel`            | `geometry_msgs/msg/Twist` | AIformula側`twist_mux` | 実機制御、`ffb_follow.py`  | 選択後の最終速度指令  |
| `/aiformula_sensing/gyro_odometry_publisher/odom` | `nav_msgs/msg/Odometry`   | オドメトリノード              | `ffb_follow.py`       | 実機の位置と向き    |

---

# ノードごとの役割

| ノード・ファイル                    | 動作場所       | 役割                     |
| --------------------------- | ---------- | ---------------------- |
| `aiformula_launch.py`       | このPC       | ノード起動、YAML指定、remap設定   |
| `handle.py`                 | このPC       | G923入力を速度指令へ変換         |
| `ffb_follow.py`             | このPC       | AIformulaの旋回挙動をG923へ反映 |
| `lane_line_controller`      | AIformula側 | 自律走行指令を生成              |
| `twist_mux`                 | AIformula側 | 自律指令と手動指令を選択           |
| `gyro_odometry_publisher`   | AIformula側 | 実機の位置と向きをpublish       |
| `ffb_follow_aiformula.yaml` | このPC       | AIformula用FFBパラメータを設定  |

---

# 起動方法

## 1. ROS_DOMAIN_IDの確認

このPCとAIformula側で同じ値を使用する。

```bash
echo $ROS_DOMAIN_ID
```

必要に応じて設定する。

```bash
export ROS_DOMAIN_ID=40
```

---

## 2. ワークスペースのビルド

```bash
cd ~/yopi_ws

colcon build \
  --symlink-install \
  --packages-select oit
```

```bash
source install/setup.bash
```

---

## 3. AIformula用Launchの起動

```bash
ros2 launch oit aiformula_launch.py
```

---

# 動作確認

## handle.pyの手動指令

```bash
ros2 topic echo \
  /aiformula_control/handle_controller/cmd_vel
```

アクセルやハンドルを操作したときに、`Twist`が出力されることを確認する。

---

## 手動介入状態

```bash
ros2 topic echo /handle/manual_active
```

操作中に`True`、操作終了後に`False`になることを確認する。

---

## AIformula側twist_muxの最終出力

```bash
ros2 topic echo \
  /aiformula_control/twist_mux/cmd_vel
```

自律走行中は自律指令、手動操作中はハンコン指令が出力されることを確認する。

---

## ffb_follow.pyの購読先

```bash
ros2 node info /ffb_follow_node
```

次のトピックを購読していることを確認する。

```text
/aiformula_control/twist_mux/cmd_vel
/aiformula_sensing/gyro_odometry_publisher/odom
/handle/manual_active
```

---

## オドメトリの更新周期

```bash
ros2 topic hz \
  /aiformula_sensing/gyro_odometry_publisher/odom
```

オドメトリが継続して更新されていることを確認する。

---

本システムでは、`handle.py`がハンコンからAIformulaへ操作情報を送る役割を持ち、`ffb_follow.py`がAIformulaからG923へ実機の挙動を返す役割を持つ。

AIformula側の`twist_mux`が自律走行指令と手動操作指令を切り替えることで、自律走行中の手動オーバーライドを実現している。
