# TFA CO2 Meter -> MQTT (Docker)

This container reads the TFA TFACO2 AirCO2ntrol meter from `/dev/hidraw0` and publishes:

- Home Assistant MQTT discovery payloads
- `CO2/state` as JSON, for example `{"co2":612,"temperature":22.31,"humidity":41.0}`
- `CO2/status` as retained `online` and `offline`

It is intended for systems where the CO2 meter is available as a HID raw device and Docker Compose is installed.

## Run Options

You can run this project in two ways:

- Build it yourself from this repository
- Use the prebuilt Docker image from GitHub Container Registry

In both cases, create your local environment file first:

```bash
cp .env.example .env
```

Set at least these values in `.env`:

- `MQTT_HOST`
- `MQTT_USER`
- `MQTT_PASS`

If your meter is not exposed as `/dev/hidraw0`, update `DEVICE_PATH` in `.env` and the device mapping in `docker-compose.yml`.

## Run From The Published Image

The included `docker-compose.yml` uses the published image and reads its values from `.env`:

```bash
docker compose up -d
```

Follow the logs:

```bash
docker compose logs -f
```

## Build And Run From Source

If you want to build the container yourself from the local repository, use:

```bash
docker build -t tfaco2-mqtt-bridge .
docker run -d \
  --name tfaco2-mqtt \
  --restart unless-stopped \
  --env-file .env \
  --device /dev/hidraw0:/dev/hidraw0 \
  tfaco2-mqtt-bridge
```

Or with Docker Compose:

```yaml
services:
  tfaco2-mqtt:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      MQTT_HOST: ${MQTT_HOST}
      MQTT_PORT: ${MQTT_PORT:-1883}
      MQTT_USER: ${MQTT_USER}
      MQTT_PASS: ${MQTT_PASS}
      MQTT_TOPIC_PREFIX: ${MQTT_TOPIC_PREFIX:-CO2}
      HA_PREFIX: ${HA_PREFIX:-homeassistant}
      HA_DISCOVERY_ENABLED: ${HA_DISCOVERY_ENABLED:-true}
      DEVICE_ID: ${DEVICE_ID:-co2meter_tfaco2}
      DEVICE_NAME: ${DEVICE_NAME:-TFA CO2 Meter}
      DEVICE_MODEL: ${DEVICE_MODEL:-TFACO2 AirCO2ntrol}
      DEVICE_MANUFACTURER: ${DEVICE_MANUFACTURER:-TFA}
      MQTT_CLIENT_ID: ${MQTT_CLIENT_ID:-co2meter_tfaco2-bridge}
      MQTT_KEEPALIVE: ${MQTT_KEEPALIVE:-60}
      DEVICE_PATH: ${DEVICE_PATH:-/dev/hidraw0}
    devices:
      - "${DEVICE_PATH:-/dev/hidraw0}:${DEVICE_PATH:-/dev/hidraw0}"
```

## Compose Example With Published Image

```yaml
services:
  tfaco2-mqtt:
    image: ghcr.io/buliwyf42/tfaco2-mqtt-bridge:latest
    restart: unless-stopped
    environment:
      MQTT_HOST: ${MQTT_HOST}
      MQTT_PORT: ${MQTT_PORT:-1883}
      MQTT_USER: ${MQTT_USER}
      MQTT_PASS: ${MQTT_PASS}
      MQTT_TOPIC_PREFIX: ${MQTT_TOPIC_PREFIX:-CO2}
      HA_PREFIX: ${HA_PREFIX:-homeassistant}
      HA_DISCOVERY_ENABLED: ${HA_DISCOVERY_ENABLED:-true}
      DEVICE_ID: ${DEVICE_ID:-co2meter_tfaco2}
      DEVICE_NAME: ${DEVICE_NAME:-TFA CO2 Meter}
      DEVICE_MODEL: ${DEVICE_MODEL:-TFACO2 AirCO2ntrol}
      DEVICE_MANUFACTURER: ${DEVICE_MANUFACTURER:-TFA}
      MQTT_CLIENT_ID: ${MQTT_CLIENT_ID:-co2meter_tfaco2-bridge}
      MQTT_KEEPALIVE: ${MQTT_KEEPALIVE:-60}
      DEVICE_PATH: ${DEVICE_PATH:-/dev/hidraw0}
    devices:
      - "${DEVICE_PATH:-/dev/hidraw0}:${DEVICE_PATH:-/dev/hidraw0}"
```

## Deployment

To deploy this project on a target host:

1. Copy the repository to the host.
2. Ensure Docker and Docker Compose are installed.
3. Create `.env` from `.env.example` and fill in your MQTT broker credentials.
4. Make sure the CO2 meter is available as `/dev/hidraw0`, or adjust `DEVICE_PATH` in `.env` and the device mapping in `docker-compose.yml`.
5. Choose one of these start methods:

From the published image:

```bash
docker compose up -d
```

From source:

```bash
docker build -t tfaco2-mqtt-bridge .
docker run -d \
  --name tfaco2-mqtt \
  --restart unless-stopped \
  --env-file .env \
  --device /dev/hidraw0:/dev/hidraw0 \
  tfaco2-mqtt-bridge
```

6. Check the container logs:

```bash
docker compose logs -f
```

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MQTT_HOST` | Yes | none | Hostname or IP address of the MQTT broker. |
| `MQTT_PORT` | No | `1883` | MQTT broker port. |
| `MQTT_USER` | Yes | none | MQTT username. |
| `MQTT_PASS` | Yes | none | MQTT password. |
| `MQTT_CLIENT_ID` | No | `co2meter_tfaco2-bridge` | MQTT client ID used by the container. |
| `MQTT_KEEPALIVE` | No | `60` | MQTT keepalive in seconds. |
| `MQTT_TOPIC_PREFIX` | No | `CO2` | Prefix for published state and availability topics. |
| `HA_PREFIX` | No | `homeassistant` | Prefix for Home Assistant MQTT discovery topics. |
| `HA_DISCOVERY_ENABLED` | No | `true` | Enable or disable Home Assistant MQTT discovery publishing. |
| `DEVICE_ID` | No | `co2meter_tfaco2` | Home Assistant device identifier. |
| `DEVICE_NAME` | No | `TFA CO2 Meter` | Home Assistant device name. |
| `DEVICE_MODEL` | No | `TFACO2 AirCO2ntrol` | Device model shown in Home Assistant. |
| `DEVICE_MANUFACTURER` | No | `TFA` | Device manufacturer shown in Home Assistant. |
| `DEVICE_PATH` | No | `/dev/hidraw0` | Path to the HID raw device exposed inside the container. |

## Home Assistant

Discovery is enabled by default and creates three sensors under one device:

- CO2
- Temperature
- Humidity

You can disable discovery with `HA_DISCOVERY_ENABLED=false` if you prefer to define entities manually.

Once the container is running and connected to your MQTT broker, Home Assistant should discover the device automatically if the MQTT integration is configured and discovery is enabled.

## Attribution

The low-level USB HID reader in `co2monitor.py` is based on the upstream
`TFACO2AirCO2ntrol_CO2Meter` project by JsBergbau and the reverse-engineering
work documented in Hackaday's "All your base are belong to us" log entry.

Sources:

- https://github.com/JsBergbau/TFACO2AirCO2ntrol_CO2Meter
- https://hackaday.io/project/5301-reverse-engineering-a-low-cost-usb-co-monitor/log/17909-all-your-base-are-belong-to-us
