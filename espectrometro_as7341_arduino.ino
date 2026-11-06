#include <Wire.h>
#include <Adafruit_AS7341.h>

Adafruit_AS7341 as7341;

void setup() {
  Serial.begin(115200);

  if (!as7341.begin()) {
    Serial.println("Sensor AS7341 nao encontrado!");
    while (1);
  }
}

void loop() {

  if (as7341.readAllChannels()) {

    // Envia os 8 canais no formato esperado pelo aplicativo
    for (int i = 0; i < 8; i++) {

      Serial.print(as7341.getChannel(i));

      if (i < 7) {
        Serial.print(",");
      }
    }

    Serial.println();
  }

  delay(500);
}