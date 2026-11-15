/* ESP32 Home IoT Monitoring & Alert System: sensor loop independent of Wi-Fi/MQTT worker.
   MQTT 3.1.1 QoS0; no guaranteed event replay. See firmware README. */
#include <Arduino.h>
#include <WiFi.h>
#include <math.h>
#include <initializer_list>
#include "rules.hpp"
#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#endif

struct Reading {
  float temperature=NAN,humidity=NAN;
  int gas=0;
  bool door=false,motion=false,pirReady=false,gasReady=false;
  uint32_t sequence=0,uptime=0;
};
struct EdgeEvent {char type[32];char transition[8];uint32_t sequence;};
Reading latest;
SemaphoreHandle_t readingMutex;
QueueHandle_t events;
ThresholdRule temperatureRule,gasRule;
DebouncedInput doorInput,motionInput;
volatile bool mqttOnline=false;
char bootId[17];
uint32_t lastSample=0;
WiFiClient tcp;

// Bound every DHT wait; invalid checksum/timing returns false, never zero data.
bool waitWhileLevel(int level,uint32_t limitUs=120) {
  uint32_t start=micros();
  while(digitalRead(DHT_PIN)==level) if(uint32_t(micros()-start)>limitUs)return false;
  return true;
}
bool readDht(float &t,float &h) {
  uint8_t bytes[5]={0};
  pinMode(DHT_PIN,OUTPUT);digitalWrite(DHT_PIN,LOW);delayMicroseconds(1200);
  digitalWrite(DHT_PIN,HIGH);delayMicroseconds(30);pinMode(DHT_PIN,INPUT_PULLUP);
  if(!waitWhileLevel(HIGH)||!waitWhileLevel(LOW)||!waitWhileLevel(HIGH))return false;
  for(int bit=0;bit<40;bit++) {
    if(!waitWhileLevel(LOW))return false;
    uint32_t start=micros();if(!waitWhileLevel(HIGH))return false;
    bytes[bit/8]=(bytes[bit/8]<<1)|(uint32_t(micros()-start)>45);
  }
  if(uint8_t(bytes[0]+bytes[1]+bytes[2]+bytes[3])!=bytes[4])return false;
  h=((bytes[0]<<8)|bytes[1])*0.1f;
  t=(((bytes[2]&0x7f)<<8)|bytes[3])*0.1f;if(bytes[2]&0x80)t=-t;
  return isfinite(t)&&isfinite(h)&&t>=-40&&t<=80&&h>=0&&h<=100;
}
String mqttString(const String &value) {
  String out;out.reserve(value.length()+2);out+=char(value.length()>>8);out+=char(value.length()&255);out+=value;return out;
}
bool sendPacket(uint8_t type,const String &body) {
  uint8_t header[5];header[0]=type;size_t n=1,len=body.length();
  do{uint8_t b=len%128;len/=128;if(len)b|=128;header[n++]=b;}while(len&&n<5);
  return tcp.write(header,n)==n && tcp.write((const uint8_t*)body.c_str(),body.length())==body.length();
}
bool publish(const char *channel,const String &json) {
  String topic=String(TOPIC_PREFIX)+"/"+DEVICE_ID+"/"+channel;
  return sendPacket(0x30,mqttString(topic)+json);
}
String statusJson(const char *status) {
  return String("{\"device_id\":\"")+DEVICE_ID+"\",\"boot_id\":\""+bootId+"\",\"status\":\""+status+"\"}";
}
bool mqttConnect() {
  tcp.stop();tcp.setTimeout(1000);
  if(!tcp.connect(MQTT_HOST,MQTT_PORT,1000))return false;
  // Clean session + QoS0 last will. Credentials optional; never printed.
  uint8_t flags=6;if(strlen(MQTT_USER))flags|=192;
  String body=mqttString("MQTT");body+=char(4);body+=char(flags);body+=char(0);body+=char(15);
  body+=mqttString(String("esp32-")+DEVICE_ID+"-"+bootId);
  body+=mqttString(String(TOPIC_PREFIX)+"/"+DEVICE_ID+"/status");body+=mqttString(statusJson("offline"));
  if(strlen(MQTT_USER)){body+=mqttString(MQTT_USER);body+=mqttString(MQTT_PASSWORD);}
  if(!sendPacket(0x10,body))return false;
  uint8_t reply[4];if(tcp.readBytes(reply,4)!=4||reply[0]!=0x20||reply[1]!=2||reply[3]!=0){tcp.stop();return false;}
  return publish("status",statusJson("online"));
}
String numberOrNull(float v){return isfinite(v)?String(v,1):String("null");}
String telemetry(const Reading &r) {
  String out="{\"device_id\":\"";out+=DEVICE_ID;out+="\",\"boot_id\":\"";out+=bootId;
  out+="\",\"source\":\"esp32\",\"timestamp\":null,\"seq\":";out+=r.sequence;
  out+=",\"uptime_ms\":";out+=r.uptime;out+=",\"temperature\":";out+=numberOrNull(r.temperature);
  out+=",\"humidity\":";out+=numberOrNull(r.humidity);out+=",\"gas\":";out+=r.gas;
  out+=",\"gas_ready\":";out+=r.gasReady?"true":"false";
  out+=",\"motion\":";out+=r.pirReady?(r.motion?"true":"false"):"null";
  out+=",\"door_open\":";out+=r.door?"true":"false";out+="}";return out;
}
void queueEvent(const char *type,const char *transition="") {
  EdgeEvent e={};strncpy(e.type,type,sizeof(e.type)-1);strncpy(e.transition,transition,sizeof(e.transition)-1);e.sequence=latest.sequence;
  if(xQueueSend(events,&e,0)!=pdTRUE){EdgeEvent discarded;xQueueReceive(events,&discarded,0);xQueueSend(events,&e,0);Serial.println("Diagnostic event queue overflow");}
}
void networkTask(void*) {
  WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  uint32_t retryAt=0,lastPublish=0,lastRx=millis(),lastPing=0,lastSequence=0;
  for(;;) {
    uint32_t now=millis();
    if(WiFi.status()!=WL_CONNECTED){mqttOnline=false;tcp.stop();if(uint32_t(now-retryAt)>5000){retryAt=now;WiFi.reconnect();}}
    else if(!tcp.connected()) {mqttOnline=false;if(uint32_t(now-retryAt)>3000){retryAt=now;if(mqttConnect()){mqttOnline=true;lastRx=now;lastSequence=0;}}}
    else {
      while(tcp.available()){tcp.read();lastRx=now;}
      if(uint32_t(now-lastRx)>30000){tcp.stop();mqttOnline=false;continue;}
      if(uint32_t(now-lastPing)>5000){lastPing=now;if(!sendPacket(0xc0,"")){tcp.stop();mqttOnline=false;}}
      Reading r;xSemaphoreTake(readingMutex,portMAX_DELAY);r=latest;xSemaphoreGive(readingMutex);
      // Never send a stale snapshot as a new heartbeat.
      if(r.sequence && r.sequence!=lastSequence && uint32_t(now-lastPublish)>=100) {
        lastPublish=now;
        if(publish("telemetry",telemetry(r)))lastSequence=r.sequence;else{tcp.stop();mqttOnline=false;}
      }
      EdgeEvent e;
      while(tcp.connected()&&xQueueReceive(events,&e,0)==pdTRUE){
        String out=String("{\"device_id\":\"")+DEVICE_ID+"\",\"boot_id\":\""+bootId+"\",\"seq\":"+String(e.sequence)+",\"event_type\":\""+e.type+"\",\"transition\":\""+e.transition+"\"}";
        publish(strlen(e.transition)?"alert":"event",out);
      }
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}
void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN,INPUT);pinMode(DOOR_PIN,INPUT_PULLUP);
  for(int pin:{BUZZER_PIN,GREEN_LED,YELLOW_LED,RED_LED}){pinMode(pin,OUTPUT);digitalWrite(pin,LOW);}
  analogReadResolution(12);analogSetPinAttenuation(GAS_PIN,ADC_11db);
  snprintf(bootId,sizeof(bootId),"%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random());
  readingMutex=xSemaphoreCreateMutex();events=xQueueCreate(16,sizeof(EdgeEvent));
  xTaskCreatePinnedToCore(networkTask,"network",8192,nullptr,1,nullptr,0);
  Serial.println("Home IoT Monitoring & Alert System started. MQTT credentials are not logged.");
}
void loop() {
  uint32_t now=millis();
  if(doorInput.update(digitalRead(DOOR_PIN)==HIGH,now))queueEvent(doorInput.stable?"DOOR_OPENED":"DOOR_CLOSED");
  bool pirReady=now>=PIR_WARMUP_MS;
  if(pirReady&&motionInput.update(digitalRead(PIR_PIN)==HIGH,now))queueEvent(motionInput.stable?"MOTION_DETECTED":"MOTION_CLEARED");
  if(uint32_t(now-lastSample)>=TELEMETRY_MS) {
    lastSample=now;Reading r;r.uptime=now;r.pirReady=pirReady;r.motion=motionInput.stable;r.door=doorInput.stable;
    r.gasReady=GAS_CONDITIONED&&now>=GAS_WARMUP_MS;
    float t=NAN,h=NAN;if(readDht(t,h)){r.temperature=t;r.humidity=h;}
    uint32_t sum=0;for(int i=0;i<8;i++)sum+=analogRead(GAS_PIN);r.gas=sum/8;
    int temperatureTransition=temperatureRule.update(r.temperature,isfinite(r.temperature),TEMPERATURE_HIGH,TEMPERATURE_CLEAR,CONFIRM_SAMPLES);
    int gasTransition=gasRule.update(r.gas,r.gasReady,GAS_HIGH,GAS_CLEAR,CONFIRM_SAMPLES);
    xSemaphoreTake(readingMutex,portMAX_DELAY);r.sequence=latest.sequence+1;latest=r;xSemaphoreGive(readingMutex);
    if(temperatureTransition)queueEvent("HIGH_TEMPERATURE",temperatureTransition>0?"active":"clear");
    if(gasTransition)queueEvent("GAS_ALERT",gasTransition>0?"active":"clear");
    Serial.printf("sample=%lu temp=%s gas=%d gas_ready=%d mqtt=%d\n",(unsigned long)r.sequence,numberOrNull(r.temperature).c_str(),r.gas,r.gasReady,mqttOnline);
  }
  bool active=temperatureRule.active||gasRule.active;
  digitalWrite(BUZZER_PIN,active?HIGH:LOW);digitalWrite(RED_LED,active?HIGH:LOW);
  digitalWrite(YELLOW_LED,(!mqttOnline||!latest.gasReady||!latest.pirReady||!isfinite(latest.temperature))?HIGH:LOW);
  digitalWrite(GREEN_LED,(mqttOnline&&!active&&latest.gasReady&&latest.pirReady&&isfinite(latest.temperature))?HIGH:LOW);
  delay(5);
}
