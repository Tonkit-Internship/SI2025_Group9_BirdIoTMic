import network
import ujson
import urequests
import time
from machine import Pin, I2C, SDCard
from config import WIFI_SSID, WIFI_PASS, DEVICE_ID, API_URL
import os
import gc
import usocket
import ssl

# เชื่อม WiFi
def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        time.sleep(0.1)
    print("WiFi connected:", wlan.ifconfig())

# เมนูนี้ใช้สำหรับ mount SD card
def mount_sd():
    sd = SDCard(slot=1)
    os.mount(sd, "/sd")
    print("SD mounted at /sd")

#อัปไฟล์เสียง
def upload_presigned_file(filepath, url):
    # แยก host และ path ออกจาก URL
    _, _, host_path = url.partition("https://")
    host, _, path = host_path.partition("/")
    path = "/" + path

    with open(filepath, "rb") as f:
        file_size = os.stat(filepath)[6]

        # สร้าง socket และเชื่อมต่อแบบ HTTPS
        addr = usocket.getaddrinfo(host, 443)[0][-1]
        s = usocket.socket()
        s.connect(addr)
        s = ssl.wrap_socket(s, server_hostname=host)

        # ส่ง HTTP PUT header
        s.write(f"PUT {path} HTTP/1.1\r\n".encode())
        s.write(f"Host: {host}\r\n".encode())
        s.write("Content-Type: audio/wav\r\n".encode())
        s.write(f"Content-Length: {file_size}\r\n".encode())
        s.write("Connection: close\r\n\r\n".encode())

        # ส่งข้อมูลไฟล์เป็น chunk
        while True:
            chunk = f.read(512)
            if not chunk:
                break
            s.write(chunk)

        # อ่าน response จาก S3
        response = b""
        try:
            while True:
                data = s.read(512)
                if not data:
                    break
                response += data
        except:
            pass

        s.close()
        print("Upload response:", response.decode())

def main():
    connect_wifi(WIFI_SSID, WIFI_PASS)
    mount_sd()

    # สร้าง metadata พร้อมชื่อไฟล์
    metadata = {
        "device_id": "ESP-001",
        "data": [
            {
                "timestamp": "2025-06-25T17:00:00Z",
                "files": ["1.wav", "2.wav", "3.wav"],
                "location": "TreeA",
                "temperature": 29.3,
                "humidity": 78.1
            }
        ]
    }

    # 1. ส่ง metadata ขอ presigned URLs
    resp = urequests.post(
        API_URL,
        data=ujson.dumps(metadata),
        headers={"Content-Type": "application/json"}
    )
    print("Metadata upload status:", resp.status_code)
    print("Response:", resp.text)
    presigned_urls = ujson.loads(resp.text)["presigned_urls"]
    resp.close()

    # 2. อัปโหลดไฟล์ .wav ทีละไฟล์โดยใช้ presigned URL
    for filename in metadata["data"][0]["files"]:
        upload_url = presigned_urls["2025-06-25T17:00:00Z"][filename]
        filepath = "/sd/testvoice/" + filename
        print("Uploading", filepath)
        upload_presigned_file(filepath, upload_url)
        gc.collect()

if __name__ == "__main__":
    main()
