/*
  FIAP GS 2025 – Nó “Flood Demo”  v2.4a
  ─────────────────────────────────────
  • SIMULATION = true  → gera dados sintéticos
  • SIMULATION = false → usa sensores reais
*/

#define SIMULATION true      // ← mude para false p/ hardware real

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "DHT.h"

/* ───── Pinagem ───────────────────── */
#define TRIG_PIN    5
#define ECHO_PIN    18
#define DHT_PIN     15
#define LED_PIN     2
#define BUZZER_PIN  27
#define DHT_TYPE    DHT22

/* ───── Limiares ──────────────────── */
#define SENSOR_HEIGHT_CM 50
#define MAX_LEVEL_CM     50
#define ALARME_CM        40

/* ───── Wi-Fi / MQTT ──────────────── */
const char* ssid       = "Wokwi-GUEST";
const char* password   = "";
const char* mqttServer = "broker.hivemq.com";
const int   mqttPort   = 1883;
const char* topic      = "fiap/gs2025/flood";

WiFiClient   net;
PubSubClient mqtt(net);
DHT          dht(DHT_PIN, DHT_TYPE);

/* ─── Funções de SIMULAÇÃO ─────────────────────────────────── */
#if SIMULATION
float simTemp() { return 28 + 4 * sin(millis() / 30000.0); }          // 24–32 °C
float simHum()  { return 60 + 20 * sin(millis() / 45000.0 + 1.5); }   // 40–80 %
long  simDist() {                                                     // 45→5→45 cm
  float p = fmod(millis() / 1000.0, 60.0);
  return (p < 30) ? 45 - p * (40.0 / 30.0)
                  :  5 + (p - 30) * (40.0 / 30.0);
}
#endif

/* ─── Medição real ─────────────────────────────────────────── */
#if !SIMULATION
long measureDistanceCm(float tempC) {
  const uint8_t N = 5;
  float v_cm_us = (331.3f + 0.606f * tempC) / 10000.0f;
  if (v_cm_us <= 0) return -1;

  long total = 0;
  for (uint8_t i = 0; i < N; ++i) {
    digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    long dur = pulseIn(ECHO_PIN, HIGH, 25000);
    if (dur == 0) return -1;
    total += dur;
    delay(10);
  }
  return (total / N) * v_cm_us / 2;
}
#endif

/* ─── Conexões de rede (com prints) ────────────────────────── */
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Wi-Fi: ");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password, 6);              // canal 6 (Wokwi)

  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 5000) {
    Serial.print('.');
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED)
    Serial.println(" conectado");
  else
    Serial.println(" falhou");
}

void connectMQTT() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;

  Serial.print("MQTT…");
  mqtt.setServer(mqttServer, mqttPort);
  if (mqtt.connect("ESP32FloodNode")) {
    Serial.println(" conectado");
    mqtt.publish(topic, "ESP32 online");
  } else {
    Serial.printf(" falha (rc=%d)\n", mqtt.state());
  }
}

/* ─── Setup ────────────────────────────────────────────────── */
void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);   pinMode(BUZZER_PIN, OUTPUT);
  noTone(BUZZER_PIN);
  if (!SIMULATION) dht.begin();

  connectWiFi();
  connectMQTT();
  Serial.println("\nFlood Demo v2.4a – " + String(SIMULATION ? "SIMULAÇÃO" : "SENSORES"));
}

/* ─── Loop ─────────────────────────────────────────────────── */
void loop() {
  static uint32_t t0 = 0;
  mqtt.loop();  connectWiFi();  connectMQTT();
  if (millis() - t0 < 1000) return;   // 1 s
  t0 = millis();

  /* Leituras */
  float temp, hum; long dist;
#if SIMULATION
  temp = simTemp(); hum = simHum(); dist = simDist();
#else
  temp = dht.readTemperature();
  hum  = dht.readHumidity();
  dist = isnan(temp) ? -1 : measureDistanceCm(temp);
#endif

  long level = (dist >= 0) ? SENSOR_HEIGHT_CM - dist : -1;
  if (level < 0) level = 0;
  float perc = level * 100.0f / MAX_LEVEL_CM;
  bool alarm = level > ALARME_CM;

  digitalWrite(LED_PIN, alarm);
  if (alarm) tone(BUZZER_PIN, 500); else noTone(BUZZER_PIN);

  /* MQTT */
  StaticJsonDocument<128> doc;
  doc["t"] = temp; doc["h"] = hum;
  doc["d"] = dist; doc["w"] = level;
  doc["p"] = perc; doc["alarm"] = alarm;
  char buf[128];  serializeJson(doc, buf);
  if (mqtt.connected()) mqtt.publish(topic, buf);

  /* Serial */
  Serial.printf("T=%.1f°C H=%.0f%% D=%ldcm N=%ldcm (%.0f%%)%s\n",
                temp, hum, dist, level, perc, alarm ? " ALERTA" : "");
}
