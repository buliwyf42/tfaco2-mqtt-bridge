#!/usr/bin/python3 -u
import fcntl
import sys


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


def hd(d):
    return " ".join("%02X" % e for e in d)


def checksum_ok(frame):
    return frame[4] == 0x0D and (sum(frame[:3]) & 0xFF) == frame[3]


if __name__ == "__main__":
    # Key retrieved from /dev/random, guaranteed to be random ;)
    key = [0xC4, 0xC6, 0xC0, 0x92, 0x40, 0x23, 0xDC, 0x96]
    if len(sys.argv) != 2:
        print("Please specify the device, usually /dev/hidraw0")
        sys.exit(1)

    fp = open(sys.argv[1], "a+b", 0)
    HIDIOCSFEATURE_9 = 0xC0094806
    set_report = bytearray([0x00] + key)
    fcntl.ioctl(fp, HIDIOCSFEATURE_9, set_report)

    values = {}
    try:
        while True:
            raw = fp.read(8)
            if len(raw) != 8:
                # Defensive: avoid index errors if the device returns a short frame.
                continue

            data = list(raw)
            decrypted = data if checksum_ok(data) else decrypt(key, data)
            if not checksum_ok(decrypted):
                print(hd(data), " => ", hd(decrypted), "Checksum error")
                continue

            op = decrypted[0]
            val = decrypted[1] << 8 | decrypted[2]
            values[op] = val

            # Output data immediately when received.
            if op == 0x50:  # CO2
                print("CO2: %4i" % values[0x50], flush=True)
            elif op == 0x42:  # Temperature
                print("T: %2.2f" % (values[0x42] / 16.0 - 273.15), flush=True)
            elif op == 0x44:  # Humidity (primary)
                print("RH: %2.2f" % (values[0x44] / 100.0), flush=True)
            elif op == 0x41 and 0x44 not in values:  # Fallback humidity
                print("RH: %2.2f" % (values[0x41] / 100.0), flush=True)
    except KeyboardInterrupt:
        pass
