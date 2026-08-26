# Smart Classroom — ESP32 Wiring Guide

Board: **ESP32 DevKit V1** (30-pin, default board for this project)

## Components

| Component            | Qty | Notes                                      |
|-----------------------|-----|---------------------------------------------|
| ESP32 DevKit V1        | 1   | 30-pin variant                              |
| Green LED (5mm)        | 1   | "attention OK" indicator                    |
| Yellow LED (5mm)       | 1   | "warning" indicator                         |
| Red LED (5mm)          | 1   | "critical" indicator                        |
| 220Ω resistor          | 3   | one per LED, current-limiting               |
| Active piezo buzzer     | 1   | 5V active buzzer (no PWM tone needed)       |
| 16x2 LCD with I2C backpack (PCF8574) | 1 | I2C address usually `0x27` or `0x3F` |
| Breadboard + jumper wires | — |                                            |
| 5V/2A USB power supply  | 1   | powers ESP32 + peripherals                  |

## Pin Assignments

| ESP32 Pin | Connects To          | Purpose                    |
|-----------|------------------------|-----------------------------|
| GPIO 25   | Green LED anode (+) via 220Ω resistor | LED_GREEN — "attention OK" |
| GPIO 26   | Yellow LED anode (+) via 220Ω resistor | LED_YELLOW — "warning"     |
| GPIO 27   | Red LED anode (+) via 220Ω resistor    | LED_RED — "critical"       |
| GPIO 14   | Buzzer (+)              | Piezo buzzer signal          |
| GPIO 21   | LCD SDA                | I2C data line                |
| GPIO 22   | LCD SCL                | I2C clock line                |
| 5V        | LCD VCC, Buzzer VCC (if separate) | Power                     |
| GND       | LED cathodes (–), Buzzer (–), LCD GND | Common ground             |

> All three LED cathodes and the buzzer's negative lead share the ESP32's
> `GND` pin (or a common ground rail on the breadboard) — do not power the
> LEDs/buzzer from a separate ground than the ESP32, or logic levels won't
> reference correctly.

## Wiring Diagram (schematic, text form)

```
                         ESP32 DevKit V1
                     ┌─────────────────────┐
                     │                     │
     Green LED ──[220Ω]── GPIO25           │
     Yellow LED ──[220Ω]── GPIO26          │
     Red LED ──[220Ω]── GPIO27             │
                     │                     │
     Buzzer(+) ────────── GPIO14           │
                     │                     │
     LCD SDA ──────────── GPIO21 (SDA)     │
     LCD SCL ──────────── GPIO22 (SCL)     │
                     │                     │
     LCD VCC ──────────── 5V               │
     LCD GND ┐                             │
     LED(-) ─┼──────────── GND ────────────┤
     Buzzer(-)┘                            │
                     │                     │
                     └─────────────────────┘
                        USB 5V/2A Power
```

Each LED: `GPIO → 220Ω resistor → LED anode (long leg) → LED cathode (short leg) → GND`.

## I2C Address Discovery

If the LCD shows nothing but the backlight is on, the I2C address in
`esp32_firmware.ino` (`LCD_I2C_ADDRESS`, default `0x27`) may not match your
specific PCF8574 backpack. Run this minimal scanner sketch to find it:

```cpp
#include <Wire.h>
void setup() {
  Wire.begin();
  Serial.begin(115200);
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("I2C device found at 0x");
      Serial.println(addr, HEX);
    }
  }
}
void loop() {}
```

Update `LCD_I2C_ADDRESS` in `esp32_firmware.ino` to whatever address is printed.

## Power Notes

- The ESP32's onboard 3.3V regulator is **not** sized to drive the LCD
  backlight + buzzer + 3 LEDs simultaneously off USB power reliably in all
  cases — using the board's 5V pin (fed from USB) for the LCD and buzzer,
  as wired above, avoids brownouts. The GPIO-driven LEDs draw only a few
  mA each through their resistors and are fine off GPIO directly.
- If the ESP32 resets unexpectedly when the buzzer fires, add a 100–470µF
  electrolytic capacitor across 5V/GND near the buzzer to smooth the
  current spike.

## Network Configuration

Set `WIFI_SSID` / `WIFI_PASSWORD` and the static IP block (`STATIC_IP`,
`GATEWAY`, `SUBNET`) at the top of `esp32_firmware.ino` to match your
classroom network. The static IP **must match** `ESP32_IP` in the
backend's `.env` file, since `esp32_service.py` talks to the device over
plain HTTP at `http://<ESP32_IP>/command`.
