#!/usr/bin/env python3
import atexit
import json
import os
import signal
import sys
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

from co2monitor import Co2Meter


def env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_bool(name, default=False):
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = env(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer value for {name}: {value}") from exc


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
        self.discovery_enabled = env_bool("HA_DISCOVERY_ENABLED", True)
        self.state_topic = f"{self.topic_prefix}/state"
        self.status_topic = f"{self.topic_prefix}/status"
        self.connect_retry_seconds = env_int("MQTT_CONNECT_RETRY_SECONDS", 5)
        self.client = mqtt.Client(
            client_id=env("MQTT_CLIENT_ID", f"{self.device_id}-bridge"),
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            clean_session=True,
        )
        self.client.username_pw_set(
            env("MQTT_USER", required=True), env("MQTT_PASS", required=True)
        )
        if env_bool("MQTT_TLS_ENABLED", False):
            ca_cert = env("MQTT_TLS_CA_CERT") or None
            certfile = env("MQTT_TLS_CERTFILE") or None
            keyfile = env("MQTT_TLS_KEYFILE") or None
            self.client.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile)
            if env_bool("MQTT_TLS_INSECURE", False):
                self.client.tls_insecure_set(True)
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
        port = env_int("MQTT_PORT", 1883)
        keepalive = env_int("MQTT_KEEPALIVE", 60)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(host, port, keepalive)
        self.client.loop_start()
        while not self.stop_event.is_set():
            if self.connected.wait(timeout=self.connect_retry_seconds):
                return
            print(
                f"Waiting for MQTT broker {host}:{port}...",
                file=sys.stderr,
                flush=True,
            )
        raise RuntimeError("Stopping before MQTT connection became available")

    def stop(self):
        self.stop_event.set()
        if self.connected.is_set():
            self.publish_status("offline", allow_failure=True)
        self.client.loop_stop()
        self.client.disconnect()

    def wait_until_connected(self):
        while not self.stop_event.is_set():
            if self.connected.wait(timeout=1):
                return
        raise RuntimeError("Stopping before MQTT connection became available")

    def publish(self, topic, payload, retain=False, allow_failure=False):
        self.wait_until_connected()
        info = self.client.publish(topic, payload=payload, qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            message = f"Failed to publish to {topic}: rc={info.rc}"
            if allow_failure:
                print(message, file=sys.stderr, flush=True)
                return False
            raise RuntimeError(message)
        return True

    def publish_status(self, payload, allow_failure=False):
        return self.publish(
            self.status_topic,
            payload,
            retain=True,
            allow_failure=allow_failure,
        )

    def publish_birth_messages(self):
        try:
            self.publish_status("online", allow_failure=True)
            if self.discovery_enabled:
                self.publish_discovery()
        except Exception as exc:
            print(f"Failed to publish discovery data: {exc}", file=sys.stderr, flush=True)

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
    meter = Co2Meter(
        device_path=env("DEVICE_PATH", "/dev/hidraw0"),
        retry_delay=float(env("DEVICE_RETRY_DELAY_SECONDS", "5")),
    )
    latest = {}
    last_payload = None

    def shutdown(signum=None, frame=None):
        bridge.stop()
        meter.close()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    atexit.register(bridge.stop)
    atexit.register(meter.close)

    bridge.connect()
    for key, value in meter.read_measurements():
        latest[key] = value
        payload = json.dumps(latest, separators=(",", ":"))
        if payload != last_payload:
            print(payload, flush=True)
            bridge.publish(bridge.state_topic, payload)
            last_payload = payload
            Path("/tmp/heartbeat").touch()


if __name__ == "__main__":
    main()
