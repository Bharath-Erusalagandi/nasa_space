// Pod K-01 early prototype on an Arduino Uno robot car kit (Uno + Sensor Shield V5).
// Prints one JSON object per line (115200 baud over USB, or 9600 through the Bluetooth module):
//   {"k":"dist","v":23.4}   ultrasonic distance in cm, twice a second
//   {"k":"light","v":62}    solar panel voltage as a percentage of the ADC range, once a second
// Commands, one per line: dispatch, drive <ms>, nod, stop.

#include <Servo.h>

// the usual wiring of these car kits; change the numbers here if yours differs
const uint8_t TRIG = A5, ECHO = A4;
const uint8_t SERVO_PIN = 3;
const uint8_t ENA = 5, ENB = 6, IN1 = 7, IN2 = 8, IN3 = 9, IN4 = 11;
const uint8_t LIGHT_PIN = A0;

// set to 1 only after the solar panel is wired to A0 through the two resistors
#define LIGHT_SENSOR 0

// 115200 over the USB cable; 9600 over the kit's Bluetooth module, the speed those modules ship at
#define BAUD 115200

const unsigned long DIST_EVERY_MS = 500;
const unsigned long LIGHT_EVERY_MS = 1000;
const unsigned long MAX_DRIVE_MS = 3000;
const uint8_t DRIVE_SPEED = 160;

Servo head;
unsigned long lastDist = 0, lastLight = 0, driveUntil = 0;
bool driving = false;
char cmd[24];
uint8_t cmdLen = 0;

float pingCm() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 25000UL);
  return us == 0 ? -1.0 : us / 58.0;
}

// median of three pings; -1 when fewer than two echoes came back
float distanceCm() {
  float v[3];
  uint8_t n = 0;
  for (uint8_t i = 0; i < 3; i++) {
    float cm = pingCm();
    if (cm >= 2.0 && cm <= 400.0) v[n++] = cm;
    delay(12);
  }
  if (n < 2) return -1.0;
  if (n == 2) return (v[0] + v[1]) / 2.0;
  float lo = min(v[0], min(v[1], v[2])), hi = max(v[0], max(v[1], v[2]));
  return v[0] + v[1] + v[2] - lo - hi;
}

void motors(bool on) {
  digitalWrite(IN1, on ? HIGH : LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, on ? HIGH : LOW);
  analogWrite(ENA, on ? DRIVE_SPEED : 0);
  analogWrite(ENB, on ? DRIVE_SPEED : 0);
  driving = on;
}

void drive(unsigned long ms) {
  if (ms > MAX_DRIVE_MS) ms = MAX_DRIVE_MS;
  driveUntil = millis() + ms;
  motors(true);
}

// the servo is attached only while it moves, so it cannot brown the board out on USB power at rest
void nod() {
  head.attach(SERVO_PIN);
  head.write(60);
  delay(220);
  head.write(120);
  delay(220);
  head.write(90);
  delay(220);
  head.detach();
}

void ack(const char *what) {
  Serial.print(F("{\"ack\":\""));
  Serial.print(what);
  Serial.println(F("\"}"));
}

void run(char *line) {
  if (strcmp(line, "dispatch") == 0) {
    nod();
    drive(1500);
    ack("dispatch");
  } else if (strncmp(line, "drive", 5) == 0) {
    long ms = atol(line + 5);
    drive(ms > 0 ? (unsigned long)ms : 1000);
    ack("drive");
  } else if (strcmp(line, "nod") == 0) {
    nod();
    ack("nod");
  } else if (strcmp(line, "stop") == 0) {
    motors(false);
    ack("stop");
  }
}

void readCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdLen > 0) {
        cmd[cmdLen] = 0;
        run(cmd);
        cmdLen = 0;
      }
    } else if (cmdLen < sizeof(cmd) - 1) {
      cmd[cmdLen++] = c;
    }
  }
}

void setup() {
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  const uint8_t outs[] = {ENA, ENB, IN1, IN2, IN3, IN4};
  for (uint8_t i = 0; i < sizeof(outs); i++) pinMode(outs[i], OUTPUT);
  motors(false);
  Serial.begin(BAUD);
  Serial.println(F("pod K-01 early prototype (Uno car kit) ready"));
}

void loop() {
  readCommands();
  unsigned long now = millis();

  if (driving && (long)(now - driveUntil) >= 0) motors(false);

  if (now - lastDist >= DIST_EVERY_MS) {
    lastDist = now;
    float cm = distanceCm();
    if (cm > 0) {
      Serial.print(F("{\"k\":\"dist\",\"v\":"));
      Serial.print(cm, 1);
      Serial.println(F("}"));
    }
  }

#if LIGHT_SENSOR
  if (now - lastLight >= LIGHT_EVERY_MS) {
    lastLight = now;
    long pct = (long)analogRead(LIGHT_PIN) * 100 / 1023;
    Serial.print(F("{\"k\":\"light\",\"v\":"));
    Serial.print(pct);
    Serial.println(F("}"));
  }
#endif
}
