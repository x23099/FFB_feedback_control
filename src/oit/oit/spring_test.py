#!/usr/bin/env python3

import time
import subprocess

from evdev import InputDevice, ecodes, ff


DEVICE_PATH = (
    '/dev/input/by-id/'
    'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
    'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
)


def set_autocenter(strength):
    """
    G923の標準センタリング力を設定する。
    Springの動きを確認するため、テスト中は弱める。
    """
    subprocess.run(
        ['ffset', DEVICE_PATH, '-a', str(strength)],
        check=False
    )


def make_spring_effect(center, coeff=0x6000, saturation=0x6000, deadband=0):
    """
    FF_SPRINGエフェクトを作る。

    center:
        バネの中心位置。
        0なら物理中心。
        正負を変えることで中心位置がずれるか確認する。

    coeff:
        バネの強さ。
        大きいほど中心へ戻す力が強い。

    saturation:
        力の上限。

    deadband:
        中心付近で力を出さない範囲。
    """

    condition = ff.Condition(
        saturation,
        saturation,
        coeff,
        coeff,
        deadband,
        center
    )

    effect = ff.Effect(
        ecodes.FF_SPRING,
        -1,
        0,
        ff.Trigger(0, 0),
        ff.Replay(5000, 0),
        ff.EffectType(
            ff_condition_effect=(condition, condition)
        )
    )

    return effect


def play_effect(dev, effect, seconds=3.0):
    """
    エフェクトを再生して、指定秒数後に停止する。
    """
    effect_id = dev.upload_effect(effect)

    print(f'play effect_id={effect_id}')
    dev.write(ecodes.EV_FF, effect_id, 1)

    time.sleep(seconds)

    print('stop')
    dev.write(ecodes.EV_FF, effect_id, 0)
    dev.erase_effect(effect_id)


def main():
    dev = InputDevice(DEVICE_PATH)
    print(f'Opened: {dev.name}')

    # Spring確認中は標準センタリングを弱める。
    set_autocenter(0)

    print('Test 1: center = 0')
    effect = make_spring_effect(center=0)
    play_effect(dev, effect, seconds=3.0)

    time.sleep(1.0)

    print('Test 2: center = +8000')
    effect = make_spring_effect(center=8000)
    play_effect(dev, effect, seconds=3.0)

    time.sleep(1.0)

    print('Test 3: center = -8000')
    effect = make_spring_effect(center=-8000)
    play_effect(dev, effect, seconds=3.0)

    # 終了時は通常の重さに戻す。
    set_autocenter(80)

    dev.close()


if __name__ == '__main__':
    main()