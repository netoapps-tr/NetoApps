// HC-SR04: VCC->5V, GND->GND, TRIG->D7, ECHO->D6
const byte TRIG_PIN = 7;
const byte ECHO_PIN = 6;

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.begin(115200);
}

void loop() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN, LOW);
  unsigned long echo = pulseIn(ECHO_PIN, HIGH, 30000UL);
  float cm = echo ? (echo * 0.0343) / 2.0 : -1.0;
  bool near = cm > 0 && cm <= 80.0;
  Serial.print("{\"distance_cm\":"); Serial.print(cm, 1);
  Serial.print(",\"presence\":"); Serial.print(near ? "true" : "false");
  Serial.println("}");
  delay(120);
}
