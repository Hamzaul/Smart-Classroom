# Smart Classroom — Hardware Module

ESP32-based classroom alert unit: 3-color LED status, buzzer, and a 16x2
I2C LCD, controlled over WiFi by the Flask backend via a small JSON HTTP
protocol.

## Contents

- `esp32_firmware/esp32_firmware.ino` — the firmware, flashed to the ESP32
- `docs/wiring_diagram.md` — full wiring guide, pin table, I2C troubleshooting

## Setup

1. **Install Arduino IDE** (2.x recommended): https://www.arduino.cc/en/software
2. **Add the ESP32 board package**: File → Preferences → "Additional Boards
   Manager URLs" → add
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`,
   then Tools → Board → Boards Manager → search "esp32" → install.
3. **Install libraries** via Tools → Manage Libraries:
   - `ArduinoJson` (Benoit Blanchon)
   - `LiquidCrystal I2C` (Frank de Brabander)
4. **Wire the hardware** per `docs/wiring_diagram.md`.
5. **Edit firmware config**: open `esp32_firmware.ino` and set `WIFI_SSID`,
   `WIFI_PASSWORD`, and the static IP block to match your network. The
   static IP must match `ESP32_IP` in the backend's `.env`.
6. **Select board + port**: Tools → Board → "ESP32 Dev Module", Tools →
   Port → (your ESP32's serial port).
7. **Upload**: click Upload. Open Serial Monitor at 115200 baud to confirm
   WiFi connects and note the printed IP address.

## Protocol Reference

The firmware exposes two HTTP endpoints on port 80, matching
`backend/services/esp32_service.py` exactly:

**`POST /command`**
```json
{"cmd": "alert", "severity": "critical", "led": "red", "buzzer_ms": 800,
 "lcd_line1": "ALERT", "lcd_line2": "Vikash - Low Attn"}
```
```json
{"cmd": "display", "lcd_line1": "Present: 22/25", "lcd_line2": "Avg Attn: 78%"}
```
```json
{"cmd": "clear"}
```

**`GET /status`** → `{"online": true, "uptime_ms": 123456, "wifi_rssi_dbm": -54, "ip": "192.168.1.50"}`

## Manual Testing (without the backend)

Once flashed and connected, test directly with `curl`:

```bash
curl -X POST http://192.168.1.50/command \
  -H "Content-Type: application/json" \
  -d '{"cmd":"alert","severity":"warning","led":"yellow","buzzer_ms":300,"lcd_line1":"Test Alert","lcd_line2":"Hello ESP32"}'

curl http://192.168.1.50/status
```

## Future Support (per project spec)

The firmware's pin/command structure leaves room for a servo (e.g. a
physical "attendance flag" or camera pan mechanism) — add a
`Servo.h`-based handler and a new `cmd` value (e.g. `"servo"`) following
the same `StaticJsonDocument` parsing pattern used for `alert`/`display`.
