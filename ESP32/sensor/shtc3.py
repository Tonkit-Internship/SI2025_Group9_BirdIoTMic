import time

class SHTC3:
    def __init__(self, i2c, addr=0x70):
        self.i2c = i2c
        self.addr = addr
        self.wake()
        time.sleep_ms(1)

    def wake(self):
        # ส่งคำสั่ง wake
        self.i2c.writeto(self.addr, b'\x35\x17')

    def sleep(self):
        # ส่งคำสั่ง sleep
        self.i2c.writeto(self.addr, b'\xB0\x98')

    def measure(self):
        # ส่งคำสั่งวัดค่าแบบไม่มี clock stretching
        self.i2c.writeto(self.addr, b'\x78\x66')
        time.sleep_ms(15)

        # อ่านข้อมูล 6 ไบต์จากเซนเซอร์
        data = self.i2c.readfrom(self.addr, 6)
        if len(data) != 6:
            raise Exception("ไม่สามารถอ่านข้อมูลจากเซนเซอร์ได้")

        # แปลงค่าดิบ
        temp_raw = data[0] << 8 | data[1]
        rh_raw = data[3] << 8 | data[4]

        # คำนวณอุณหภูมิและความชื้น
        temperature = -45 + 175 * (temp_raw / 65535.0)
        humidity = 100 * (rh_raw / 65535.0)

        return temperature, humidity

