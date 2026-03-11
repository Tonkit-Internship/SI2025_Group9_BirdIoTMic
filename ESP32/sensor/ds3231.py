import utime

class DS3231:
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x68

    def bcd2dec(self, b):
        return (b >> 4) * 10 + (b & 0x0F)

    def dec2bcd(self, d):
        return (d // 10) << 4 | (d % 10)

    def datetime(self):
        data = self.i2c.readfrom_mem(self.addr, 0x00, 7)
        ss = self.bcd2dec(data[0])
        mm = self.bcd2dec(data[1])
        hh = self.bcd2dec(data[2])
        d  = self.bcd2dec(data[4])
        m  = self.bcd2dec(data[5])
        y  = self.bcd2dec(data[6]) + 2000
        return (y, m, d, hh, mm, ss)

    def set_datetime(self, dt):
        y, m, d, hh, mm, ss = dt
        data = bytes([
            self.dec2bcd(ss),
            self.dec2bcd(mm),
            self.dec2bcd(hh),
            0,
            self.dec2bcd(d),
            self.dec2bcd(m),
            self.dec2bcd(y-2000)
        ])
        self.i2c.writeto_mem(self.addr, 0x00, data)
