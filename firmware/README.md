# Pod K-01 firmware

`pod_k01/pod_k01.ino` reads a MAX30101 pulse sensor and an optional air sensor and prints one JSON event per line on USB serial at 115200 baud. The app reads those lines through Web Serial and adds the pod id and the time itself.

This firmware compiles but has not been run on a board until a person records that here.

## Wiring

All sensors share the XIAO's I2C pins. Qwiic cables carry 3.3 V, so power everything from the XIAO's 3V3 pin.

| XIAO nRF52840 pin | MAX30101 Qwiic (0x57) | SHT31 (0x44) or BME280 (0x76 / 0x77) |
|---|---|---|
| 3V3 | 3.3V | VIN or VCC |
| GND | GND | GND |
| D4 (SDA) | SDA | SDA |
| D5 (SCL) | SCL | SCL |

The air sensor is optional. At start the firmware looks for an SHT31 at 0x44, then a BME280 at 0x76, then 0x77, and uses the first one it finds. A BMP280 has no humidity and is not detected. Mount the air sensor outside the box on a 10 to 15 cm lead, on the shaded underside, as plan section A6 says.

## Libraries

These versions compiled the sketch on 2026-11-14 with arduino-cli 1.6.0:

| Library or core | Version |
|---|---|
| Seeeduino:nrf52 (board package) | 1.1.13 |
| SparkFun MAX3010x Pulse and Proximity Sensor Library | 1.1.2 |
| Adafruit SHT31 Library | 2.2.2 |
| Adafruit BME280 Library | 2.3.0 |
| Adafruit BusIO (installed with the Adafruit libraries) | 1.17.4 |
| Adafruit Unified Sensor (installed with the BME280 library) | 1.1.15 |
| adafruit-nrfutil (the board package calls it to build the upload file) | 0.5.3.post16 |

The heart rate code uses `heartRate.h` and the SpO2 code uses `spo2_algorithm.h`, both from the SparkFun library.

## Build and flash

Arduino IDE: add `https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json` under Preferences, Additional boards manager URLs. Install "Seeed nRF52 Boards" (not the "mbed-enabled" package) and the three libraries above. Choose "Seeed XIAO nRF52840" or "Seeed XIAO nRF52840 Sense", pick the port and press Upload.

arduino-cli, from the repo root:

```
arduino-cli config add board_manager.additional_urls https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json
arduino-cli core update-index
arduino-cli core install Seeeduino:nrf52
arduino-cli lib install "SparkFun MAX3010x Pulse and Proximity Sensor Library" "Adafruit SHT31 Library" "Adafruit BME280 Library"
arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840 firmware/pod_k01
arduino-cli upload --fqbn Seeeduino:nrf52:xiaonRF52840 -p <port> firmware/pod_k01
```

Use `Seeeduino:nrf52:xiaonRF52840Sense` for the Sense board. On Linux, `pip install adafruit-nrfutil` first if the compile stops with "adafruit-nrfutil: executable file not found". If the upload cannot find the board, double-tap the reset button to enter the bootloader and try again.

## What the pod prints

At boot, plain text lines. The app ignores them.

```
pod K-01 starting
pulse sensor: MAX30101 at 0x57
air sensor: SHT31 at 0x44
pod K-01 ready
```

The second line reads `pulse sensor: not found, retrying` when the MAX30101 does not answer; the firmware then tries again every 2 seconds and prints the found line when it comes up. The third line reads `air sensor: BME280 at 0x76`, `air sensor: BME280 at 0x77` or `air sensor: none found`.

Event lines, one JSON object per line:

```
{"k":"hr","v":72,"q":0.88}
{"k":"spo2","v":98,"q":0.80}
{"k":"temp","v":24.1}
{"k":"rh","v":41}
```

The numbers here show the format only; they are not measurements.

- `hr`: heart rate in beats per minute, an integer, about once a second.
- `spo2`: oxygen saturation in percent, an integer, about once a second.
- `temp`: air temperature in °C with one decimal, every 2 seconds.
- `rh`: relative humidity in percent, an integer, every 2 seconds.

`hr` and `spo2` are printed only while a finger is on the sensor (infrared reading above 50000) and the value is valid as described below. With no finger, nothing is printed for them. `temp` and `rh` are printed only when an air sensor was found at start and the read succeeded.

If the loop ever falls behind the sensor, the firmware prints `pulse sensor: samples lost, readings restarted` and builds the heart rate and SpO2 values again from new samples.

## How the values and q are worked out

The MAX30101 runs red and infrared at 100 samples per second. Beat-to-beat intervals are timed by counting samples (10 ms each), using `checkForBeat` from `heartRate.h`. Intervals outside 30 to 220 bpm are dropped. The last 8 intervals are kept.

- `hr` value: 60000 divided by the median of the kept intervals, rounded. Printed when at least 4 intervals are kept and a beat came in the last 3 seconds.
- `hr` q: the number of the last 8 interval slots that hold an interval within 15 percent of their median, divided by 8, so an empty slot counts against it.
- `spo2` value: once a second the firmware runs `maxim_heart_rate_and_oxygen_saturation` from `spo2_algorithm.h` on the last 4 seconds of samples (averaged down to 25 per second, as that function expects). A run counts as valid when the function marks it valid and the result is 70 to 100. The value is the median of the valid results among the last 5 runs, printed when at least 3 of them are valid.
- `spo2` q: the number of valid runs among the last 5, divided by 5.

Taking the finger off clears all of this, so a new finger starts from empty.

q measures how steady the sensor's own readings are. It is not an accuracy figure. The SpO2 function comes with the library and has not been calibrated against a reference for this board; the hardware validation in `docs/VALIDATION.md` is where accuracy gets measured.

## Not checked without hardware

- That the board boots and the lines above appear on a real serial port.
- That 50000 is the right infrared level for finger detection with this LED setting, through the enclosure's finger slot.
- That the loop keeps up with the sensor (no "samples lost" lines) while the SHT31 read, which waits about 20 ms, is running.
- Heart rate and SpO2 against a reference oximeter.
- Air sensor detection at each address, and temperature and humidity values.

## Early prototype on an Arduino Uno robot car kit (`pod_uno`)

A stand-in built from parts on hand, to show the loop end to end before the real pod exists. It has no pulse, air or mosquito sensor.

- The ultrasonic sensor, pointed down at a surface, sends `{"k":"dist","v":23.4}` twice a second (centimetres, 2 to 400).
- A small solar panel wired to A0 through a two-resistor divider sends `{"k":"light","v":62}` once a second: the panel voltage as a percentage of the 5 V input range, uncalibrated. Set `LIGHT_SENSOR` to 1 only after wiring it. Never connect the panel straight to a pin.
- Commands, one per line: `dispatch` (the servo nods, then the car drives forward for 1.5 s), `drive <ms>` (3000 at most), `nod`, `stop`. Each one answers `{"ack":"<command>"}`.

The Mission screen shows the two readings in GROUND when they arrive, sends `dispatch` when a delivery is planned, and prints the car's acknowledgement under Delivery. `public/pod-test.html` is a one-page test of the same lines with no other code.

Board: Arduino Uno, 115200 baud over USB.

Over Bluetooth instead of the cable: set `BAUD` to 9600 at the top of the sketch, upload with the Bluetooth module unplugged, then plug it back in, pair it with the Mac (its usual name is HC-05 or HC-06, PIN 1234 or 0000), and press Connect pod in Chrome and pick it. The pod line then says "Connected over Bluetooth". Chrome reads a paired Bluetooth serial module through the same Web Serial API.

Pins assumed (the usual wiring of these kits, change them at the top of the sketch): Trig A5, Echo A4, servo 3, motor driver ENA 5, ENB 6, IN1 7, IN2 8, IN3 9, IN4 11. Unplug the Bluetooth module while uploading and while the USB cable is in use, because it shares the serial pins.

The sketch compiles for `arduino:avr:uno`. It has not been run on a board by the authors of this repo.
