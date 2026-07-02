#!/usr/bin/env python3

import argparse
import subprocess
import time

from evdev import InputDevice, ecodes, ff


DEVICE_PATH = (
    '/dev/input/by-id/'
    'usb-Logitech_G923_Racing_Wheel_for_PlayStation_4_and_PC_'
    'USYMUGUXEREJOFORUFUMEZIDU-event-joystick'
)


WAVEFORMS = {
    'square': ecodes.FF_SQUARE,
    'sine': ecodes.FF_SINE,
    'triangle': ecodes.FF_TRIANGLE,
}


def set_autocenter(device_path, strength):
    subprocess.run(
        ['ffset', device_path, '-a', str(int(strength))],
        check=False
    )


def make_periodic_effect(
    waveform,
    magnitude,
    period_ms,
    duration_ms,
    effect_id=-1
):
    envelope = ff.Envelope(
        0,
        0,
        int(duration_ms),
        0
    )

    periodic = ff.Periodic(
        waveform,
        int(period_ms),
        int(magnitude),
        0,
        0,
        envelope,
        0,
        None
    )

    return ff.Effect(
        ecodes.FF_PERIODIC,
        effect_id,
        0x4000,
        ff.Trigger(0, 0),
        ff.Replay(int(duration_ms), 0),
        ff.EffectType(
            ff_periodic_effect=periodic
        )
    )


def play_once(dev, effect):
    effect_id = dev.upload_effect(effect)
    print(f'play effect_id={effect_id}')
    dev.write(ecodes.EV_FF, effect_id, 1)
    time.sleep(effect.ff_replay.length / 1000.0 + 0.2)
    dev.write(ecodes.EV_FF, effect_id, 0)
    dev.erase_effect(effect_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default=DEVICE_PATH)
    parser.add_argument(
        '--waveform',
        choices=sorted(WAVEFORMS),
        default='square'
    )
    parser.add_argument('--magnitude', type=int, default=32767)
    parser.add_argument('--period-ms', type=int, default=35)
    parser.add_argument('--duration-ms', type=int, default=1000)
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--interval-sec', type=float, default=0.5)
    parser.add_argument('--autocenter', type=int, default=0)
    args = parser.parse_args()

    dev = InputDevice(args.device)
    print(f'Opened: {dev.name}')
    print(
        f'waveform={args.waveform}, '
        f'magnitude={args.magnitude}, '
        f'period_ms={args.period_ms}, '
        f'duration_ms={args.duration_ms}'
    )

    set_autocenter(args.device, args.autocenter)

    try:
        for index in range(args.repeat):
            print(f'Test {index + 1}/{args.repeat}')
            effect = make_periodic_effect(
                waveform=WAVEFORMS[args.waveform],
                magnitude=args.magnitude,
                period_ms=args.period_ms,
                duration_ms=args.duration_ms
            )
            play_once(dev, effect)
            time.sleep(args.interval_sec)

    finally:
        set_autocenter(args.device, 80)
        dev.close()


if __name__ == '__main__':
    main()
