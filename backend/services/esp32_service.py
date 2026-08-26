"""
backend/services/esp32_service.py

ESP32 Service.

Handles outbound communication with the classroom ESP32 device over
either WiFi (HTTP POST to the ESP32's local web server) or USB Serial,
selectable via configuration. The ESP32 firmware (see /hardware) exposes
a simple JSON command protocol:

    {"cmd": "alert", "severity": "warning", "led": "yellow", "buzzer_ms": 500,
     "lcd_line1": "Low Attention!", "lcd_line2": "Check Priya Singh"}

    {"cmd": "clear"}

This service never crashes the main application if the ESP32 is
unreachable (classroom hardware is optional / best-effort) — failures
are logged and swallowed after retries.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("smart_classroom.esp32_service")

_SEVERITY_TO_LED = {
    "info": "green",
    "warning": "yellow",
    "critical": "red",
}
_SEVERITY_TO_BUZZER_MS = {
    "info": 0,
    "warning": 300,
    "critical": 800,
}


class ESP32ConnectionError(Exception):
    pass


@dataclass
class ESP32Status:
    online: bool
    last_success: Optional[float]
    last_error: Optional[str]


class ESP32Service:
    """
    Usage:
        esp32 = ESP32Service(mode="wifi", esp32_ip="192.168.1.50")
        esp32.trigger_alert(severity="critical", message="Vikash Yadav - Very low attention")
        esp32.clear()
        esp32.display_summary(present=22, total=25, avg_attention=78.6)
    """

    def __init__(
        self,
        mode: str = "wifi",
        esp32_ip: str = "192.168.1.50",
        serial_port: str = "/dev/ttyUSB0",
        serial_baud: int = 115200,
        http_timeout_seconds: float = 2.0,
        max_retries: int = 2,
    ):
        if mode not in ("wifi", "serial", "disabled"):
            raise ValueError("mode must be one of: wifi, serial, disabled")
        self._mode = mode
        self._esp32_ip = esp32_ip
        self._serial_port = serial_port
        self._serial_baud = serial_baud
        self._timeout = http_timeout_seconds
        self._max_retries = max_retries
        self._serial_conn = None  # lazily opened
        self._last_success: Optional[float] = None
        self._last_error: Optional[str] = None

        if mode == "serial":
            self._init_serial()

    def _init_serial(self) -> None:
        try:
            import serial  # pyserial, only required in serial mode

            self._serial_conn = serial.Serial(
                self._serial_port, self._serial_baud, timeout=self._timeout
            )
            logger.info("Opened serial connection to ESP32 on %s", self._serial_port)
        except Exception as e:
            logger.warning("Could not open serial port %s: %s", self._serial_port, e)
            self._serial_conn = None

    # ------------------------------------------------------------------
    def trigger_alert(self, severity: str, message: str) -> bool:
        payload = {
            "cmd": "alert",
            "severity": severity,
            "led": _SEVERITY_TO_LED.get(severity, "yellow"),
            "buzzer_ms": _SEVERITY_TO_BUZZER_MS.get(severity, 300),
            "lcd_line1": "ALERT" if severity == "critical" else "Notice",
            "lcd_line2": message[:16],  # 16x2 LCD width
        }
        return self._send(payload)

    def display_summary(self, present: int, total: int, avg_attention: float) -> bool:
        payload = {
            "cmd": "display",
            "lcd_line1": f"Present: {present}/{total}",
            "lcd_line2": f"Avg Attn: {avg_attention:.0f}%",
        }
        return self._send(payload)

    def clear(self) -> bool:
        return self._send({"cmd": "clear"})

    def get_status(self) -> ESP32Status:
        return ESP32Status(
            online=self._last_error is None and self._last_success is not None,
            last_success=self._last_success,
            last_error=self._last_error,
        )

    # ------------------------------------------------------------------
    def _send(self, payload: dict) -> bool:
        if self._mode == "disabled":
            return False

        for attempt in range(1, self._max_retries + 1):
            try:
                if self._mode == "wifi":
                    self._send_http(payload)
                else:
                    self._send_serial(payload)
                self._last_success = time.time()
                self._last_error = None
                return True
            except Exception as e:
                self._last_error = str(e)
                logger.warning(
                    "ESP32 send attempt %d/%d failed: %s",
                    attempt,
                    self._max_retries,
                    e,
                )
                time.sleep(0.2)

        logger.error("ESP32 unreachable after %d attempts; continuing without hardware alert", self._max_retries)
        return False

    def _send_http(self, payload: dict) -> None:
        url = f"http://{self._esp32_ip}/command"
        response = requests.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()

    def _send_serial(self, payload: dict) -> None:
        if self._serial_conn is None:
            self._init_serial()
        if self._serial_conn is None:
            raise ESP32ConnectionError("Serial connection not available")
        line = json.dumps(payload) + "\n"
        self._serial_conn.write(line.encode("utf-8"))
        self._serial_conn.flush()
