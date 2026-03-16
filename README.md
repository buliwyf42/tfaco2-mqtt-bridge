# TFA CO2 Meter -> MQTT (Docker)

This container reads the TFA TFACO2 AirCO2ntrol meter from `/dev/hidraw0` and publishes:

- Home Assistant MQTT discovery payloads
- `CO2/state` as JSON, for example `{"co2":612,"temperature":22.31,"humidity":41.0}`
- `CO2/status` as retained `online` and `offline`

The current Raspberry Pi service uses `co2monitor.py | mosquitto_pub`, which is why MQTT failures currently break the sensor reader with `BrokenPipeError`. This project keeps the HID reader but moves MQTT and Home Assistant discovery into one Python process with one persistent broker connection.

## Configure

```bash
cp .env.example .env
```

Set at least:

- `MQTT_HOST`
- `MQTT_USER`
- `MQTT_PASS`

If your meter is not exposed as `/dev/hidraw0`, update `DEVICE_PATH` in `.env` and the device mapping in `docker-compose.yml`.

## Run

```bash
docker compose up -d --build
docker compose logs -f
```

## Home Assistant

Discovery is enabled by default and creates three sensors under one device:

- CO2
- Temperature
- Humidity

You can disable discovery with `HA_DISCOVERY_ENABLED=false` if you prefer to define entities manually.

## Deploy On `co2-monitor.home.lan`

1. Stop the old service: `sudo systemctl disable --now co2mqtt.service`
2. Copy this project to the host
3. Create `.env` with the broker credentials currently stored in `/etc/default/co2mqtt`
4. Start the container: `docker compose up -d --build`

The Pi already has Docker and Docker Compose installed.

## Attribution

The low-level USB HID reader in `co2monitor.py` is based on the upstream
`TFACO2AirCO2ntrol_CO2Meter` project by JsBergbau and the reverse-engineering
work documented in Hackaday's "All your base are belong to us" log entry.

Sources:

- https://github.com/JsBergbau/TFACO2AirCO2ntrol_CO2Meter
- https://hackaday.io/project/5301-reverse-engineering-a-low-cost-usb-co-monitor/log/17909-all-your-base-are-belong-to-us
