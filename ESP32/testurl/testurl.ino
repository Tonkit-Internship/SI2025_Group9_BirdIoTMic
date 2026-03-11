#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h> 

// ==========================================================
// 1. กำหนดข้อมูล WiFi ของคุณ
// ==========================================================
#define WIFI_SSID "412aisfibre_2.4G" 
#define WIFI_PASSWORD "Ponmgolf" 



// ==========================================================
// 2. กำหนด AWS IoT Endpoint และ Topic
// ==========================================================
#define AWS_IOT_ENDPOINT "a2bzwg2fn7q384-ats.iot.us-east-1.amazonaws.com" 
// Topic ที่ ESP32 จะ Publish ไปเพื่อขอ Pre-signed URL (ต้องตรงกับ Rule ใน Lambda)
#define AWS_IOT_TOPIC_PUBLISH "esp32/upload/request"
// Topic ที่ ESP32 จะ Subscribe เพื่อรับ Pre-signed URL กลับมา (ต้องตรงกับ responseTopic ใน Lambda Payload)
#define AWS_IOT_TOPIC_SUBSCRIBE "esp32/upload/response"



// ==========================================================
// 3. กำหนดข้อมูล Certificate และ Private Key ของ AWS IoT
// ==========================================================
// Root CA Certificate
// คัดลอกเนื้อหาจากไฟล์ "AmazonRootCA1.pem" ที่ดาวน์โหลดมา
const char* AWS_CERT_CA = \
"-----BEGIN CERTIFICATE-----\n" \
"MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF\n" \
"ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UEChMGQW1hem9uMRkwFwYDVQQDExBBbWF6\n" \
"b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL\n" \
"MAkGA1UEBhMCVVMxDzANBgNVBAoTBkFtYXpvbjEZMBcGA1UEAxMQQW1hem9uIFJv\n" \
"b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj\n" \
"ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM\n" \
"9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw\n" \
"IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6\n" \
"VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L\n" \
"93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm\n" \
"jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC\n" \
"AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA\n" \
"A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI\n" \
"U5PMCCjjmCXPI6T53iHTfIUJrU6adTrCC2qJeHZERxhlbI1Bjjt/msv0tadQ1wUs\n" \
"N+gDS63pYaACbvXy8MWy7Vu33PqUXHeeE6V/Uq2V8viTO96LXFvKWlJbYK8U90vv\n" \
"o/ufQJVtMVT8QtPHRh8jrdkPSHCa2XV4cdFyQzR1bldZwgJcJmApzyMZFo6IQ6XU\n" \
"5MsI+yMRQ+hDKXJioaldXgjUkK642M4UwtBV8ob2xJNDd2ZhwLnoQdeXeGADbkpy\n" \
"rqXRfboQnoZsG4q5WTP468SQvvG5\n" \
"-----END CERTIFICATE-----\n"; 

// Device Certificate
// คัดลอกเนื้อหาจากไฟล์ "xxx-certificate.pem.crt" ที่ดาวน์โหลดมา
const char* AWS_CERT_CRT = \
"-----BEGIN CERTIFICATE-----\n" \
"MIIDWTCCAkGgAwIBAgIUeMS62CLRRMrXh2Gbspe+1QEqCzcwDQYJKoZIhvcNAQEL\n" \
"BQAwTTFLMEkGA1UECwxCQW1hem9uIFdlYiBTZXJ2aWNlcyBPPUFtYXpvbi5jb20g\n" \
"SW5jLiBMPVNlYXR0bGUgU1Q9V2FzaGluZ3RvbiBDPVVTMB4XDTI1MDYxNzExMjAw\n" \
"MloXDTQ5MTIzMTIzNTk1OVowHjEcMBoGA1UEAwwTQVdTIElvVCBDZXJ0aWZpY2F0\n" \
"ZTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALRvZR7uqUL/1eZcRQP0\n" \
"BzOYODAwrMO3n6cAAPGNn50TQTlW+RfEJo/0hSjCP3Dz3UYi40n27QGUJ+EpZH3E\n" \
"Uy0EfW6b0CvIqzUywLBpPhCUUZrjAxWh4dHLvZgqJlunTHVbZpTNjdC3GXtWOFA6\n" \
"Wz+1dDcYaohpXi8IkWDJ39T5qdWHh6IRD+/hXvrmFuAl/alw3CRRdiPTcPIrB0uJ\n" \
"QMm8pWTSXKw2YBOf3Z7EZvi5VwaXIViu3sZaw2WSfpd+hYnbNCV/cyRyZScFlZda\n" \
"cx1GV9earBU9iNjP5Kx3vqIG239zkq/UOJ2cPa1HDFB+KD2c8MBwFkU1D7lQHm/g\n" \
"bIcCAwEAAaNgMF4wHwYDVR0jBBgwFoAUUW24c5hERN571jl8wPNOLCDHwWUwHQYD\n" \
"VR0OBBYEFIQdXEDxtXDvFU8ZsH8aZC9PXxhHMAwGA1UdEwEB/wQCMAAwDgYDVR0P\n" \
"AQH/BAQDAgeAMA0GCSqGSIb3DQEBCwUAA4IBAQALA6I7SzzafBoqnhylXIKtXxg0\n" \
"+RbfF+wu7xEG4EGKBliNWfYEzSeVTG6qprfnclS2n6PcvAt0eUbNQL0BkpCvmKjm\n" \
"pJ7LUc5Iy4Rh+Pe+lJ9wxkILfJvFt0hArsS8HEektpkgxVMm1A1kOfmeLk3Ewx6U\n" \
"G6HBgbqH0rifnL+pVLnftg++eVJVHqxORE2Ggp91PKdcNjjRFsZvRNMWhigpO9N2\n" \
"WICDv3TY5C9nwzawwpRnpoxTMz0g09TBdI8SI3Py/k/GF42J20uMlDcnNykZ0vVb\n" \
"sAAp8EKLbI7rgUqMU3y2g5h0aMpxO0Uc07OdsAc5FNd8Pwyvxt/R5Jj+2pDN\n" \
"-----END CERTIFICATE-----\n"; 

// Private Key
// คัดลอกเนื้อหาจากไฟล์ "xxx-private.pem.key" ที่ดาวน์โหลดมา
const char* AWS_CERT_PRIVATE = \
"-----BEGIN RSA PRIVATE KEY-----\n" \
"MIIEpAIBAAKCAQEAtG9lHu6pQv/V5lxFA/QHM5g4MDCsw7efpwAA8Y2fnRNBOVb5\n" \
"F8Qmj/SFKMI/cPPdRiLjSfbtAZQn4SlkfcRTLQR9bpvQK8irNTLAsGk+EJRRmuMD\n" \
"FaHh0cu9mComW6dMdVtmlM2N0LcZe1Y4UDpbP7V0NxhqiGleLwiRYMnf1Pmp1YeH\n" \
"ohEP7+Fe+uYW4CX9qXDcJFF2I9Nw8isHS4lAybylZNJcrDZgE5/dnsRm+LlXBpch\n" \
"WK7exlrDZZJ+l36Fids0JX9zJHJlJwWVl1pzHUZX15qsFT2I2M/krHe+ogbbf3OS\n" \
"r9Q4nZw9rUcMUH4oPZzwwHAWRTUPuVAeb+BshwIDAQABAoIBAQCZaaVGuZE8oB2U\n" \
"MZuUkuWUnrYXcytRdUzPRxeGSe4ONZLdV++On35SI4scbpxWQ2I+AefSuZomH3wQ\n" \
"24rPzB8URZ8Ibn5+262GG9Ltq23T1ufTk3TJ7cv8/wgC2sOmZgaCOeZsWqFbdnK6\n" \
"BUL4I8X10yguuBnMRhqITvacnsgrYXXEX4JML86yvvI/o62EETmEEF9c23AnmHvz\n" \
"ZWJGaz8O19j/9nNzetwxTvWm9ZKQmMohlhyFIiHOZfzFJ8ENlYYP5jDjNZlEZOTm\n" \
"pWJDRZl0ZkQUTtOnxPqXD6aXQVdfjEqTR0xilNho+4l3tVY1MzxS1uKbT1C8idVe\n" \
"7uhNEqwhAoGBANy+h853hi80dpO1tyRz2cS1tISt3owFD9nUSkl9EVvm0z/6dnko\n" \
"sZ7svpxb0Gs/xF8w/kN91U+3QKQrikqQ0Fuaiu8o+iQyVgg+G/V8dvMk6qB89adz\n" \
"RmomiUnSREI+jty4eOp62xtNtFTB8t5QWA1gDBfpw/3WBu/CBEijfWAfAoGBANFA\n" \
"w4uAOXkez3xkysTZcbad7NKZ1tWiYs0QEhge882TJtAHuSUsxM8P/HLJqzZ5CSIp\n" \
"9u2zA8s9tPhMkBJ7ZhmqKPLKAmz0kDk+Bit5BnMRzWvePzXCvNhQAQWuuxPIbIu6\n" \
"+sTUXnonOpE4AL+ua4H1tSKFH/rwokkzSVbjJsaZAoGAcEl3GZ6RIkgEnWSNEbzg\n" \
"pIBtoCQ1lXIpuvuTAkjdYKtNADlutHjvyVDSMQU/Qp8ATA/G9xv2OwOTnS8MvJtn\n" \
"cYFudPOaMnlsa+r0G+7BLzOzKgoGh7RKuEp8AZI06KGb2Ej6MQRnmj7voUG7Qj0K\n" \
"XVtjK3LdIK0TgDhoJ28Koq8CgYEApvqgUEylEEMG3UPtDsJZ3JkPJ0t9xQKNBwhA\n" \
"+CCS+sPnH/BZzRF5h6ZBFDRbvN8+65VDJ5FHgMKgC9fEzArOgcJoZL3Qy7Mo95TI\n" \
"BZ7RB7f4DZDPLg5U9eR5vFgfjvzLqYEupSy2q5FsSf+/kTYVMiKpRX+n8m5dgj47\n" \
"0ur2wVkCgYB6Qk2j0BmbYX4qqNBnfaI3Ku41mLNRRzjMxRv42SadC6wew8zno+cr\n" \
"xPWFTM0ZE9veoOCMQicuyXI6zL0tKueE7TNE9TvsxxBaygVAsRtPJNrnW1SKVFxt\n" \
"VP36/CusLmbDkfKB+LIA3aayMkX4gm+a3frgpQl4j/p325nkJWkGEA==\n" \
"-----END RSA PRIVATE KEY-----\n";

// ==========================================================

WiFiClientSecure net;
PubSubClient client(net);
long lastMsg = 0; // สำหรับนับเวลา Publish message
int msgCount = 0; // นับจำนวน message ที่ส่ง

// ฟังก์ชันเชื่อมต่อ Wi-Fi
void connectWiFi() {
  Serial.print("Connecting to Wi-Fi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected.");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

// Callback Function เมื่อได้รับข้อความ MQTT
void messageHandler(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message received on topic: ");
  Serial.println(topic);

  // แปลง payload เป็น String
  char message[length + 1];
  strncpy(message, (char*)payload, length);
  message[length] = '\0'; // ใส่ null terminator
  Serial.println(message);

  // Parse JSON message
  StaticJsonDocument<512> doc; // ขนาด Doc ตามที่คาดว่า payload จะมี
  DeserializationError error = deserializeJson(doc, message);

  if (error) {
    Serial.print(F("deserializeJson() failed: "));
    Serial.println(error.f_str());
    return;
  }

  // ดึงค่าจาก JSON
  const char* fileId = doc["fileId"];
  const char* uploadUrl = doc["uploadUrl"];
  const char* errorMsg = doc["error"]; // ถ้ามี error

  if (errorMsg) {
    Serial.print("Error from Lambda: ");
    Serial.println(errorMsg);
  } else if (uploadUrl) {
    Serial.print("Received Upload URL for fileId ");
    Serial.print(fileId);
    Serial.print(": ");
    Serial.println(uploadUrl);
    // *** คุณสามารถเพิ่มโค้ดสำหรับอัปโหลดไฟล์เสียงไปยัง URL นี้ได้ที่นี่ ***
    // เช่น การใช้ HTTPClient หรือไลบรารีอื่น
    // ตัวอย่างเช่น: startFileUpload(uploadUrl, fileId);
  } else {
    Serial.println("Received unknown response from Lambda.");
  }
}


// ฟังก์ชันเชื่อมต่อ AWS IoT MQTT
void connectAWS() {
  // กำหนด Certificate ให้กับ WiFiClientSecure
  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);

  // กำหนด MQTT Server และ Port
  client.setServer(AWS_IOT_ENDPOINT, 8883);
  client.setCallback(messageHandler); // กำหนดฟังก์ชันสำหรับรับข้อความ

  Serial.println("Connecting to AWS IoT...");
  while (!client.connected()) {
    // client.connect(clientId)
    // clientId ควรเป็นชื่อ Thing ของคุณ (MyESP32Device) หรืออะไรก็ได้ที่ไม่ซ้ำกัน
    // ใช้ Thing name เพื่อให้ AWS IoT สามารถติดตามสถานะ Thing ได้
    if (client.connect("MyESP32Device")) { // <<<< เปลี่ยนเป็นชื่อ Thing ของคุณ
      Serial.println("AWS IoT Connected!");
      // Subscribe เพื่อรอรับ Pre-signed URL
      client.subscribe(AWS_IOT_TOPIC_SUBSCRIBE);
      Serial.print("Subscribed to topic: ");
      Serial.println(AWS_IOT_TOPIC_SUBSCRIBE);
    } else {
      Serial.print("Failed to connect to AWS IoT, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds...");
      delay(5000);
    }
  }
}

// ฟังก์ชัน Publish ข้อความ
void publishMessage() {
  StaticJsonDocument<256> doc; // ขนาด Document สำหรับ JSON Payload
  doc["filename"] = "esp32_audio_" + String(msgCount) + ".wav"; // ชื่อไฟล์แบบ dynamic
  doc["contentType"] = "audio/wav";
  doc["fileId"] = "esp32_id_" + String(msgCount);
  doc["responseTopic"] = AWS_IOT_TOPIC_SUBSCRIBE; // ให้ Lambda ส่ง URL กลับมาที่ Topic นี้

  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);

  Serial.print("Publishing message to topic: ");
  Serial.println(AWS_IOT_TOPIC_PUBLISH);
  Serial.println(jsonBuffer);

  client.publish(AWS_IOT_TOPIC_PUBLISH, jsonBuffer);
}

void setup() {
  Serial.begin(115200);
  connectWiFi();
  connectAWS();
}

void loop() {
  if (!client.connected()) {
    connectAWS(); // พยายามเชื่อมต่อใหม่ถ้าหลุด
  }
  client.loop(); // ต้องเรียก loop() ตลอดเวลา เพื่อให้ PubSubClient ทำงาน

  long now = millis();
  if (now - lastMsg > 10000) { // ส่งข้อความทุก 10 วินาที
    lastMsg = now;
    msgCount++;
    publishMessage();
  }
}