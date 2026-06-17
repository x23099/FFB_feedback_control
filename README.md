# FFB_feedback_control #
## 概要 ##
### aiformula_launch.py ###
 handle.py, ffb_follow.pyの起動
 トピックの接続先,yamlの設定の指定
 
 •ffb_follow_aiformula.yaml
  aiformula用のFFB設定ファイルでffb_follow.pyがどのトピックを見るかを指定している
  auto_cmd_topic(自律走行) : /twist_mux/cmd_vel
  odom_topic(車体の向き) : /aiformula_sensing/gyro_odometry_publisher/odom
  manual_active_topic(操作介入してるか) : /handle/manual_active
  をそれぞれffb_follow.pyの中のffb_follow_nodeに渡す

 •handle.pyのremap
  このノードを起動すると本来は/cmd_vel_joyを操作指令として
  出すが、aiformula用にremapするので/aiformula_control/twist_mux/cmd_vel
  に指令が出される(メッセージの型はgeometry_msgs/msg/Twist)
  また、このノードは/handle/manual_active(メッセージの型はstd_msgs/msg/Bool)も
  pubしており、人間が操作中かどうかをTure or Falseで出力する

