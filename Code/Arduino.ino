#include <Servo.h>

Servo servoX;
Servo servoY;

const int servoX_pin = 9;
const int servoY_pin = 10;

void setup() {
  Serial.begin(9600);
  servoX.attach(servoX_pin);
  servoY.attach(servoY_pin);

  servoX.write(90); // Center
  servoY.write(90); // Center
  delay(500);
  Serial.println("Arduino ready");
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();
    if (data.length() == 0) return;

    if (data == "PING") {
      Serial.println("PONG");
      return;
    }

    int commaIndex = data.indexOf(',');
    if (commaIndex > 0) {
      int x = data.substring(0, commaIndex).toInt();
      int y = data.substring(commaIndex + 1).toInt();

      x = constrain(x, 0, 180);
      y = constrain(y, 0, 180);

      servoX.write(x);
      servoY.write(y);

      Serial.print("Received: ");
      Serial.print(x);
      Serial.print(",");
      Serial.println(y);
    }
  }
}
