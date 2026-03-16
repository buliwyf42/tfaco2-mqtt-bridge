# TFA CO2 Meter -> MQTT (Docker)

This container reads the TFA TFACO2 AirCO2ntrol meter from `/dev/hidraw0` and publishes:

- Home Assistant MQTT discovery payloads
- `CO2/state` as JSON, for example `{"co2":612,"temperature":22.31,"humidity":41.0}`
- `CO2/status` as retained `online` and `offline`

It is intended for systems where the CO2 meter is available as a HID raw device and Docker Compose is installed.

## Getting Started

Clone the repository and create your local environment file:

```bash
cp .env.example .env
```

Set at least these values in `.env`:

- `MQTT_HOST`
- `MQTT_USER`
- `MQTT_PASS`

If your meter is not exposed as `/dev/hidraw0`, update `DEVICE_PATH` in `.env` and the device mapping in `docker-compose.yml`.

Start the container:

```bash
docker compose up -d --build
```

Follow the logs:

```bash
docker compose logs -f
```

## Deployment

To deploy this project on a target host:

1. Copy the repository to the host.
2. Ensure Docker and Docker Compose are installed.
3. Create `.env` from `.env.example` and fill in your MQTT broker credentials.
4. Make sure the CO2 meter is available as `/dev/hidraw0`, or adjust `DEVICE_PATH` in `.env` and the device mapping in `docker-compose.yml`.
5. Start the container:

```bash
docker compose up -d --build
```

6. Check the container logs:

```bash
docker compose logs -f
```

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
