#!/usr/bin/env python3
import atexit
import fcntl
import json
import os
import signal
import sys
import threading

import paho.mqtt.client as mqtt


KEY = [0xC4, 0xC6, 0xC0, 0x92, 0x40, 0x23, 0xDC, 0x96]
HIDIOCSFEATURE_9 = 0xC0094806


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


def env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Co2Meter:
    def __init__(self, device_path):
        self.device_path = device_path
        self.fp = None
        self.values = {}

    def open(self):
        self.fp = open(self.device_path, "a+b", 0)
        fcntl.ioctl(self.fp, HIDIOCSFEATURE_9, bytearray([0x00] + KEY))

    def read_forever(self):
        if self.fp is None:
            self.open()

        while True:
            raw = self.fp.read(8)
            if len(raw) != 8:
                continue

            data = list(raw)
            frame = data if checksum_ok(data) else decrypt(KEY, data)
            if not checksum_ok(frame):
                continue

            op = frame[0]
            val = (frame[1] << 8) | frame[2]
            self.values[op] = val

            if op == 0x50:
                yield ("co2", self.values[0x50])
            elif op == 0x42:
                yield ("temperature", round(self.values[0x42] / 16.0 - 273.15, 2))
            elif op == 0x44:
                yield ("humidity", round(self.values[0x44] / 100.0, 2))
            elif op == 0x41 and 0x44 not in self.values:
                yield ("humidity", round(self.values[0x41] / 100.0, 2))


class MqttBridge:
    def __init__(self):
        self.stop_event = threading.Event()
        self.connected = threading.Event()
        self.topic_prefix = env("MQTT_TOPIC_PREFIX", "CO2").rstrip("/")
        self.ha_prefix = env("HA_PREFIX", "homeassistant").rstrip("/")
        self.device_id = env("DEVICE_ID", "co2meter_tfaco2")
        self.device_name = env("DEVICE_NAME", "TFA CO2 Meter")
        self.device_model = env("DEVICE_MODEL", "TFACO2 AirCO2ntrol")
        self.device_manufacturer = env("DEVICE_MANUFACTURER", "TFA")
        self.discovery_enabled = env("HA_DISCOVERY_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.state_topic = f"{self.topic_prefix}/state"
        self.status_topic = f"{self.topic_prefix}/status"
        self.client = mqtt.Client(
            client_id=env("MQTT_CLIENT_ID", f"{self.device_id}-bridge"),
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            clean_session=True,
        )
        self.client.username_pw_set(
            env("MQTT_USER", required=True), env("MQTT_PASS", required=True)
        )
        self.client.will_set(self.status_topic, payload="offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.connected.set()
            print("Connected to MQTT broker", flush=True)
            threading.Thread(target=self.publish_birth_messages, daemon=True).start()
        else:
            print(
                f"MQTT connection failed with rc={reason_code}",
                file=sys.stderr,
                flush=True,
            )

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected.clear()
        if not self.stop_event.is_set():
            print(
                f"Disconnected from MQTT broker (rc={reason_code})",
                file=sys.stderr,
                flush=True,
            )

    def connect(self):
        host = env("MQTT_HOST", required=True)
        port = int(env("MQTT_PORT", "1883"))
        keepalive = int(env("MQTT_KEEPALIVE", "60"))
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(host, port, keepalive)
        self.client.loop_start()
        if not self.connected.wait(timeout=15):
            raise RuntimeError(f"Timed out connecting to MQTT broker {host}:{port}")

    def stop(self):
        self.stop_event.set()
        if self.connected.is_set():
            self.publish_status("offline")
        self.client.loop_stop()
        self.client.disconnect()

    def wait_until_connected(self):
        while not self.stop_event.is_set():
            if self.connected.wait(timeout=1):
                return
        raise RuntimeError("Stopping before MQTT connection became available")

    def publish(self, topic, payload, retain=False):
        self.wait_until_connected()
        info = self.client.publish(topic, payload=payload, qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Failed to publish to {topic}: rc={info.rc}")

    def publish_status(self, payload):
        self.publish(self.status_topic, payload, retain=True)

    def publish_birth_messages(self):
        self.publish_status("online")
        if self.discovery_enabled:
            self.publish_discovery()

    def discovery_payload(self, name, unique_id, unit, device_class, value_template):
        return {
            "name": name,
            "unique_id": unique_id,
            "state_topic": self.state_topic,
            "value_template": value_template,
            "unit_of_measurement": unit,
            "device_class": device_class,
            "state_class": "measurement",
            "availability_topic": self.status_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": {
                "identifiers": [self.device_id],
                "name": self.device_name,
                "manufacturer": self.device_manufacturer,
                "model": self.device_model,
            },
        }

    def publish_discovery(self):
        sensors = {
            "co2": self.discovery_payload(
                "CO2 Meter CO2",
                f"{self.device_id}_co2",
                "ppm",
                "carbon_dioxide",
                "{{ value_json.co2 }}",
            ),
            "temperature": self.discovery_payload(
                "CO2 Meter Temperature",
                f"{self.device_id}_temperature",
                "°C",
                "temperature",
                "{{ value_json.temperature }}",
            ),
            "humidity": self.discovery_payload(
                "CO2 Meter Humidity",
                f"{self.device_id}_humidity",
                "%",
                "humidity",
                "{{ value_json.humidity }}",
            ),
        }
        for key, payload in sensors.items():
            topic = f"{self.ha_prefix}/sensor/{self.device_id}/{key}/config"
            self.publish(topic, json.dumps(payload, separators=(",", ":")), retain=True)


def main():
    bridge = MqttBridge()
    meter = Co2Meter(env("DEVICE_PATH", "/dev/hidraw0"))
    latest = {}

    def shutdown(signum=None, frame=None):
        bridge.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    atexit.register(bridge.stop)

    bridge.connect()
    for key, value in meter.read_forever():
        latest[key] = value
        payload = json.dumps(latest, separators=(",", ":"))
        print(payload, flush=True)
        bridge.publish(bridge.state_topic, payload)


if __name__ == "__main__":
    main()
