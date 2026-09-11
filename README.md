# IoT AC Energy Monitor — Raspberry Pi Pico W

A Wi-Fi connected AC power and energy monitor built on the Raspberry Pi Pico W. It measures true RMS voltage (ZMPT101B) and true RMS current (ACS712 5A), calculates real-time power and cumulative energy consumption, displays live readings on a 16x2 I2C LCD, and pushes periodic updates to a Telegram chat.

## ⚠️ Safety Warning

This project connects sensors directly to **mains AC voltage** (110V/220V/230V depending on your region). Mains voltage is dangerous and can cause serious injury, electric shock, or fire if wired incorrectly.

- Only attempt this if you're experienced with mains wiring, or working under the supervision of someone who is.
- Always de-energize the circuit before wiring the ZMPT101B or ACS712's high-voltage side.
- Never touch sensor terminals or screw connectors while the circuit is live.
- Double-check all wiring before applying power.
- The author(s) of this project are not responsible for any injury, damage, or loss resulting from its use.

## ⚠️ Security Warning — Rotate Your Telegram Token

The uploaded script has a **Telegram bot token and chat ID hardcoded directly in the source**. If this file has been shared, uploaded, or committed anywhere, **that token should be treated as compromised** — regenerate it via [@BotFather](https://t.me/BotFather) immediately, and never commit real tokens to a public repo. See [Configuration](#configuration) below for a safer pattern using a separate, gitignored config file.

## Features

- True RMS voltage measurement (ZMPT101B)
- True RMS current measurement (ACS712 5A)
- Real-time power calculation (Watts)
- Cumulative energy tracking (kWh)
- Live readings on a 16x2 I2C LCD display
- Automatic I2C address detection for the LCD
- Wi-Fi connectivity with connection timeout handling
- Periodic Telegram notifications with live readings
- Noise-floor filtering to avoid false current readings near 0A

## Hardware Required

| Component | Notes |
|---|---|
| Raspberry Pi Pico W | Runs MicroPython |
| ZMPT101B AC voltage sensor module | Includes onboard isolation transformer + signal conditioning |
| ACS712 current sensor (5A version) | Hall-effect based, 185 mV/A sensitivity |
| Voltage divider resistors | Scales ACS712's 5V-referenced output into the Pico's 3.3V ADC range (see script for exact values used) |
| 16x2 I2C LCD (with PCF8574-based backpack) | Status/readings display |
| Breadboard / perfboard + jumper wires | For prototyping |
| Mains AC wiring accessories | Enclosure, fuse, appropriate connectors — use proper safety practices |

## Software Requirements

- MicroPython firmware flashed onto the Pico W
- [`pico_i2c_lcd`](https://github.com/T-622/RPI-PICO-I2C-LCD) driver library (and its `lcd_api` dependency) copied onto the Pico's filesystem
- `urequests` and `ujson` (included in most MicroPython builds with networking support; confirm availability on your firmware build)

## Wiring / Pinout

### ZMPT101B (Voltage) → Pico W

| ZMPT101B Pin | Pico W Pin |
|---|---|
| VCC | Per module spec (3.3V or 5V — check your board) |
| GND | GND |
| OUT | GP27 (ADC1) |
| L / N (screw terminals) | In series with mains AC line |

### ACS712 (Current) → Pico W

| ACS712 Pin | Pico W Pin |
|---|---|
| VCC | 5V |
| GND | GND |
| OUT | → voltage divider → GP26 (ADC0) |
| IP+ / IP- | In series with the AC load's current path |

### I2C LCD → Pico W

| LCD Backpack Pin | Pico W Pin |
|---|---|
| VCC | 5V or 3.3V (check your backpack's spec) |
| GND | GND |
| SDA | GP0 |
| SCL | GP1 |

The LCD's I2C address is auto-detected at startup via a bus scan — no need to hardcode it.

## How It Works

1. **Voltage sampling:** `read_volt_rms()` takes 1000 samples spaced 200µs apart, computes the mean (dynamic DC offset), then calculates true RMS via the sum-of-squares method, before scaling by a calibration constant into real Volts.
2. **Current sampling:** `read_ac_current_rms()` samples continuously for a 100ms window, similarly computing a dynamic mean and true RMS, then converts to Amps using the ACS712's effective sensitivity (adjusted for the voltage divider).
3. **Power & Energy:** Real power is calculated as `V_rms × I_rms × Power Factor` (assumed 1.0 for resistive loads). Energy is accumulated each loop by integrating power against the actual elapsed time since the last reading, converted to kWh.
4. **Display:** Each loop updates the LCD with current V/I/P/kWh readings.
5. **Notifications:** Every `TELEGRAM_SEND_INTERVAL_SEC` seconds, a formatted summary is POSTed to the Telegram Bot API for the configured chat.

## Configuration

Before running, update these values in the script (or better, move them to a separate `config.py` that you `.gitignore`):

```python
# Wi-Fi
WIFI_SSID = "your-network-name"
WIFI_PASSWORD = "your-network-password"

# Telegram
TELEGRAM_BOT_TOKEN = "your-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"
TELEGRAM_SEND_INTERVAL_SEC = 15
```

Recommended safer pattern:

```python
# config.py (add this file to .gitignore, do NOT commit it)
WIFI_SSID = "your-network-name"
WIFI_PASSWORD = "your-network-password"
TELEGRAM_BOT_TOKEN = "your-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"
```

```python
# Complete.py
from config import WIFI_SSID, WIFI_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

## Calibration

Both sensors must be calibrated against a known reference before trusting the readings.

**Voltage (ZMPT101B) — `CALIBRATION` constant:**
1. Temporarily set `CALIBRATION = 1.0`.
2. Run the script and note the printed raw RMS ADC voltage.
3. Measure actual mains voltage with a multimeter at the same moment.
4. `CALIBRATION = multimeter_reading / raw_rms_voltage`
5. Update the constant.

**Current (ACS712) — divider & sensitivity constants:**
1. Compare readings against a clamp meter under a known steady load.
2. If consistently off, fine-tune `R_TOP` / `R_BOTTOM` to match your actual resistor values (measure them with a multimeter — real-world resistors vary from their labeled value), or introduce a separate correction multiplier.

## Configuration Constants Reference

| Constant | Purpose |
|---|---|
| `VREF` | ADC reference voltage (3.3V on Pico W) |
| `ADC_RESOLUTION` | 4095 — code shifts `read_u16() >> 4` down to native 12-bit range |
| `SAMPLES` / `SAMPLE_INTERVAL_US` | Voltage sampling count/spacing |
| `SAMPLE_WINDOW_MS` | Current sampling duration |
| `NOISE_FLOOR_A` | Minimum current threshold to filter ambient/noise readings |
| `POWER_FACTOR` | Assumed power factor (1.0 for resistive loads; lower for motors/electronics) |
| `TELEGRAM_SEND_INTERVAL_SEC` | How often a Telegram update is sent |

## Running the Project

1. Flash MicroPython onto the Pico W.
2. Copy `Complete.py`, `pico_i2c_lcd.py`, and `lcd_api.py` onto the Pico.
3. Wire the sensors and LCD as described above.
4. Update Wi-Fi and Telegram credentials (see [Configuration](#configuration)).
5. Run the script. On boot it will:
   - Connect to Wi-Fi
   - Detect and initialize the LCD
   - Begin the sampling/display/notification loop

## Known Limitations

- Assumes a fixed **Power Factor** — real power for inductive/capacitive loads (motors, LED drivers, chargers) may be overestimated unless true phase-shift measurement is added.
- `total_energy_wh` resets on every reboot; no persistent storage across power cycles yet.
- Telegram messages are sent via blocking HTTP POST calls, which can briefly stall the sampling loop — acceptable for a periodic notification but worth knowing.
- Component tolerances mean every unit should be individually calibrated; constants are not universal across boards.
- Not a substitute for a certified/billing-grade energy meter.

## Roadmap / Possible Improvements

- [ ] Move secrets into a gitignored `config.py` or `secrets.py`
- [ ] Persistent energy storage across reboots
- [ ] True Power Factor measurement via simultaneous V/I sampling
- [ ] Web dashboard using the Pico W's onboard Wi-Fi
- [ ] Multi-channel monitoring support


## Disclaimer

This project is provided for educational and hobbyist purposes. Working with mains AC voltage carries inherent risk. Build and use at your own risk.
