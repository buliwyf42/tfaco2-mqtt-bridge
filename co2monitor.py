#!/usr/bin/env python3
import argparse
import fcntl
import sys
import time


KEY = [0xC4, 0xC6, 0xC0, 0x92, 0x40, 0x23, 0xDC, 0x96]
HIDIOCSFEATURE_9 = 0xC0094806
DEFAULT_DEVICE = "/dev/hidraw0"


def decrypt(key, data):
    cstate = [0x48, 0x74, 0x65, 0x6D, 0x70, 0x39, 0x39, 0x65]
    shuffle = [2, 4, 0, 7, 1, 6, 5, 3]
    phase1 = [0] * 8
    for i, o in enumerate(shuffle):
        phase1[o] = data[i]
    phase2 = [0] * 8
    for i in range(8):
        phase2[i] = phase1[i] ^ key[i]
    phase3 = [0] * 8
    for i in range(8):
        phase3[i] = ((phase2[i] >> 3) | (phase2[(i - 1 + 8) % 8] << 5)) & 0xFF
    ctmp = [0] * 8
    for i in range(8):
        ctmp[i] = ((cstate[i] >> 4) | (cstate[i] << 4)) & 0xFF
    out = [0] * 8
    for i in range(8):
        out[i] = (0x100 + phase3[i] - ctmp[i]) & 0xFF
    return out


def checksum_ok(frame):
    return frame[4] == 0x0D and (sum(frame[:3]) & 0xFF) == frame[3]


def hex_dump(data):
    return " ".join(f"{value:02X}" for value in data)


class Co2Meter:
    def __init__(self, device_path=DEFAULT_DEVICE, retry_delay=5.0):
        self.device_path = device_path
        self.retry_delay = retry_delay
        self.fp = None
        self.values = {}

    def open(self):
        self.close()
        self.fp = open(self.device_path, "a+b", 0)
        fcntl.ioctl(self.fp, HIDIOCSFEATURE_9, bytearray([0x00] + KEY))

    def close(self):
        if self.fp is not None:
            self.fp.close()
            self.fp = None

    def _read_frame(self):
        raw = self.fp.read(8)
        if len(raw) != 8:
            raise OSError("short HID read")

        data = list(raw)
        frame = data if checksum_ok(data) else decrypt(KEY, data)
        if not checksum_ok(frame):
            raise ValueError(f"checksum error: {hex_dump(data)} => {hex_dump(frame)}")
        return frame

    def read_measurements(self):
        while True:
            try:
                if self.fp is None:
                    self.open()

                frame = self._read_frame()
                op = frame[0]
                val = (frame[1] << 8) | frame[2]
                self.values[op] = val

                if op == 0x50:
                    yield ("co2", self.values[0x50])
                elif op == 0x42:
                    yield ("temperature", round(self.values[0x42] / 16.0 - 273.15, 1))
                elif op == 0x44:
                    yield ("humidity", round(self.values[0x44] / 100.0, 1))
                elif op == 0x41 and 0x44 not in self.values:
                    yield ("humidity", round(self.values[0x41] / 100.0, 1))
            except ValueError as exc:
                print(exc, file=sys.stderr, flush=True)
            except OSError as exc:
                print(
                    f"CO2 meter read failed on {self.device_path}: {exc}. "
                    f"Retrying in {self.retry_delay:.1f}s...",
                    file=sys.stderr,
                    flush=True,
                )
                self.close()
                time.sleep(self.retry_delay)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read a TFA TFACO2 AirCO2ntrol CO2 meter from a hidraw device."
    )
    parser.add_argument(
        "device",
        nargs="?",
        default=DEFAULT_DEVICE,
        help=f"HID device path (default: {DEFAULT_DEVICE})",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=5.0,
        help="Seconds to wait before retrying after device errors.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    meter = Co2Meter(device_path=args.device, retry_delay=args.retry_delay)
    try:
        for key, value in meter.read_measurements():
            if key == "co2":
                print(f"CO2: {value:4d}", flush=True)
            elif key == "temperature":
                print(f"T: {value:0.1f}", flush=True)
            elif key == "humidity":
                print(f"RH: {value:0.1f}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        meter.close()


if __name__ == "__main__":
    main()
