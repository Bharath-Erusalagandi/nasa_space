// pod K-01: MAX30101 pulse and SpO2 plus an optional SHT31 or BME280 air sensor,
// one JSON event per line on USB serial at 115200.

#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"
#include "spo2_algorithm.h"
#include <Adafruit_SHT31.h>
#include <Adafruit_BME280.h>

const uint32_t FINGER_IR = 50000;
const uint16_t SAMPLE_HZ = 100;
const uint8_t DECIMATE = 4;
const uint16_t SPO2_LEN = 100;
const uint16_t SPO2_STEP = 25;
const uint8_t BEATS = 8;
const uint8_t SPO2_RUNS = 5;
const uint32_t BEAT_TIMEOUT = 3 * SAMPLE_HZ;
const uint32_t REPORT_MS = 1000;
const uint32_t AIR_MS = 2000;
const uint32_t RETRY_MS = 2000;

MAX30105 pulse;
Adafruit_SHT31 sht;
Adafruit_BME280 bme;

enum Air { AIR_NONE, AIR_SHT31, AIR_BME280 };
Air air = AIR_NONE;
bool pulseOk = false;

uint32_t sampleN = 0;
bool finger = false;

uint32_t lastBeatN = 0;
bool haveLastBeat = false;
uint16_t intervals[BEATS];
uint8_t nIntervals = 0;
uint8_t intervalHead = 0;

uint32_t irBuf[SPO2_LEN];
uint32_t redBuf[SPO2_LEN];
uint16_t nBuf = 0;
uint16_t sinceRun = 0;
uint32_t irAcc = 0, redAcc = 0;
uint8_t nAcc = 0;
int8_t spo2Runs[SPO2_RUNS];
uint8_t nRuns = 0;
uint8_t runHead = 0;

uint32_t lastReport = 0, lastAir = 0, lastRetry = 0;

bool present(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

bool startPulse() {
  if (!pulse.begin(Wire, I2C_SPEED_FAST)) return false;
  // 400 samples/s averaged by 4 gives 100 Hz, red and IR
  pulse.setup(0x1F, 4, 2, 400, 411, 4096);
  return true;
}

void startAir() {
  if (present(0x44) && sht.begin(0x44)) {
    air = AIR_SHT31;
    Serial.println("air sensor: SHT31 at 0x44");
  } else if (present(0x76) && bme.begin(0x76, &Wire)) {
    air = AIR_BME280;
    Serial.println("air sensor: BME280 at 0x76");
  } else if (present(0x77) && bme.begin(0x77, &Wire)) {
    air = AIR_BME280;
    Serial.println("air sensor: BME280 at 0x77");
  } else {
    Serial.println("air sensor: none found");
  }
}

void resetReadings() {
  haveLastBeat = false;
  nIntervals = intervalHead = 0;
  nBuf = sinceRun = 0;
  irAcc = redAcc = nAcc = 0;
  nRuns = runHead = 0;
}

void addInterval(uint16_t ms) {
  intervals[intervalHead] = ms;
  intervalHead = (intervalHead + 1) % BEATS;
  if (nIntervals < BEATS) nIntervals++;
}

template <typename T>
T median(const T *src, uint8_t n) {
  T v[BEATS > SPO2_RUNS ? BEATS : SPO2_RUNS];
  for (uint8_t i = 0; i < n; i++) v[i] = src[i];
  for (uint8_t i = 1; i < n; i++)
    for (uint8_t j = i; j > 0 && v[j - 1] > v[j]; j--) {
      T t = v[j]; v[j] = v[j - 1]; v[j - 1] = t;
    }
  return n % 2 ? v[n / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;
}

void runSpo2() {
  int32_t spo2, hr;
  int8_t spo2Valid, hrValid;
  maxim_heart_rate_and_oxygen_saturation(irBuf, SPO2_LEN, redBuf, &spo2, &spo2Valid, &hr, &hrValid);
  spo2Runs[runHead] = (spo2Valid && spo2 >= 70 && spo2 <= 100) ? spo2 : -1;
  runHead = (runHead + 1) % SPO2_RUNS;
  if (nRuns < SPO2_RUNS) nRuns++;
}

void addSpo2Sample(uint32_t red, uint32_t ir) {
  redAcc += red;
  irAcc += ir;
  if (++nAcc < DECIMATE) return;
  if (nBuf == SPO2_LEN) {
    memmove(irBuf, irBuf + 1, (SPO2_LEN - 1) * sizeof(uint32_t));
    memmove(redBuf, redBuf + 1, (SPO2_LEN - 1) * sizeof(uint32_t));
    nBuf--;
  }
  irBuf[nBuf] = irAcc / DECIMATE;
  redBuf[nBuf] = redAcc / DECIMATE;
  nBuf++;
  irAcc = redAcc = nAcc = 0;
  if (nBuf == SPO2_LEN && ++sinceRun >= SPO2_STEP) {
    sinceRun = 0;
    runSpo2();
  }
}

void onSample(uint32_t red, uint32_t ir) {
  sampleN++;
  bool on = ir > FINGER_IR;
  if (on != finger) {
    finger = on;
    resetReadings();
  }
  if (!finger) return;

  if (checkForBeat(ir)) {
    if (haveLastBeat) {
      uint32_t ms = (sampleN - lastBeatN) * 1000 / SAMPLE_HZ;
      if (ms >= 60000 / 220 && ms <= 60000 / 30) addInterval(ms);
    }
    lastBeatN = sampleN;
    haveLastBeat = true;
  }
  addSpo2Sample(red, ir);
}

void drainFifo() {
  uint16_t got = pulse.check();
  // the library keeps only 3 samples between check() calls, more means a gap
  if (got > 3) {
    sampleN += got;
    resetReadings();
    while (pulse.available()) pulse.nextSample();
    Serial.println("pulse sensor: samples lost, readings restarted");
    return;
  }
  while (pulse.available()) {
    onSample(pulse.getFIFORed(), pulse.getFIFOIR());
    pulse.nextSample();
  }
}

void reportHeartRate() {
  if (nIntervals < 4 || sampleN - lastBeatN > BEAT_TIMEOUT) return;
  uint16_t med = median(intervals, nIntervals);
  uint8_t near = 0;
  for (uint8_t i = 0; i < nIntervals; i++)
    if (abs((int)intervals[i] - (int)med) * 100 <= 15 * med) near++;
  Serial.print("{\"k\":\"hr\",\"v\":");
  Serial.print((60000 + med / 2) / med);
  Serial.print(",\"q\":");
  Serial.print((float)near / BEATS, 2);
  Serial.println("}");
}

void reportSpo2() {
  int8_t valid[SPO2_RUNS];
  uint8_t n = 0;
  for (uint8_t i = 0; i < nRuns; i++)
    if (spo2Runs[i] >= 0) valid[n++] = spo2Runs[i];
  if (n < 3) return;
  Serial.print("{\"k\":\"spo2\",\"v\":");
  Serial.print((int)median(valid, n));
  Serial.print(",\"q\":");
  Serial.print((float)n / SPO2_RUNS, 2);
  Serial.println("}");
}

void reportAir() {
  float t = NAN, rh = NAN;
  if (air == AIR_SHT31) {
    sht.readBoth(&t, &rh);
  } else if (air == AIR_BME280) {
    t = bme.readTemperature();
    rh = bme.readHumidity();
  }
  if (!isnan(t)) {
    Serial.print("{\"k\":\"temp\",\"v\":");
    Serial.print(t, 1);
    Serial.println("}");
  }
  if (!isnan(rh)) {
    Serial.print("{\"k\":\"rh\",\"v\":");
    Serial.print((long)lroundf(rh));
    Serial.println("}");
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}
  Serial.println("pod K-01 starting");
  Wire.begin();
  pulseOk = startPulse();
  Serial.println(pulseOk ? "pulse sensor: MAX30101 at 0x57" : "pulse sensor: not found, retrying");
  startAir();
  Wire.setClock(400000);
  Serial.println("pod K-01 ready");
}

void loop() {
  uint32_t now = millis();
  if (!pulseOk) {
    if (now - lastRetry >= RETRY_MS) {
      lastRetry = now;
      pulseOk = startPulse();
      if (pulseOk) Serial.println("pulse sensor: MAX30101 at 0x57");
    }
  } else {
    drainFifo();
    if (now - lastReport >= REPORT_MS) {
      lastReport = now;
      if (finger) {
        reportHeartRate();
        reportSpo2();
      }
    }
  }

  if (air != AIR_NONE && now - lastAir >= AIR_MS) {
    lastAir = now;
    reportAir();
    if (pulseOk) drainFifo();
  }
}
