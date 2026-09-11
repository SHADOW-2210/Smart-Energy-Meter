from machine import SoftI2C, Pin, ADC
from pico_i2c_lcd import I2cLcd
import network
import urequests
import ujson
import time
import math

led = Pin('LED', Pin.OUT)
led.value(1)
time.sleep(1)

#LCD Display Declaration
LCD_ROWS = 2
LCD_COLS = 16
sda_pin = 0
scl_pin = 1

volt_adc = ADC(Pin(27))  
current_adc = ADC(Pin(26))

#ZMPT101B Calibaration
SAMPLES = 1000          
SAMPLE_INTERVAL_US = 200  
CALIBRATION = 190

#ACS712 Calibaration
VREF = 3.3
ADC_RESOLUTION = 4095
R_TOP = 967       
R_BOTTOM = 1439    
DIVIDER_RATIO = R_BOTTOM / (R_TOP + R_BOTTOM)
RAW_SENSITIVITY = 0.185           
EFFECTIVE_SENSITIVITY = RAW_SENSITIVITY * DIVIDER_RATIO
SAMPLE_WINDOW_MS = 100            
NOISE_FLOOR_A = 0.08

#considering pure resistive load
POWER_FACTOR = 1.0 
total_energy_wh = 0.0

#WIFI Details
WIFI_SSID = "High Tide Gamer"
WIFI_PASSWORD = "12345678"

#Declaration of Telegram Bot
TELEGRAM_BOT_TOKEN = "8809065437:AAG4TukWKbMOpsPGkSL_txwsfcG7COtHhEQ"  
TELEGRAM_CHAT_ID = "2032289962"                                
TELEGRAM_SEND_INTERVAL_SEC = 15

#display
def detect_lcd_address(i2c):
    devices = i2c.scan()
    if not devices:
        raise RuntimeError(
            f"No I2C device found on SDA={sda_pin}, SCL={scl_pin} - check your wiring."
        )
    return devices[0]


#Connection to WIFI
def connect_wifi(ssid, password, timeout_sec=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_sec * 1000:
                raise RuntimeError("Wi-Fi connection timed out")
            time.sleep_ms(500)
    print("Wi-Fi connected, IP:", wlan.ifconfig()[0])
    time.sleep(2)
    return wlan
 
#Telegram Massage/Notification 
def send_telegram_message(text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = urequests.post(url, json=payload)
        response.close()
    except Exception as e:
        print("Telegram send failed:", e)

#Reading Current RMS
def read_ac_current_rms():
    samples = []
    start_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_time) < SAMPLE_WINDOW_MS:
        raw = current_adc.read_u16()>>4
        voltage = (raw * VREF) / ADC_RESOLUTION
        samples.append(voltage)

    if len(samples) == 0:
        return 0.0
    mean_voltage = sum(samples) / len(samples)
    sum_squared = 0.0
    for v in samples:
        centered = v - mean_voltage
        sum_squared += centered * centered
    mean_square = sum_squared / len(samples)
    v_rms = math.sqrt(mean_square)
    
    i_rms = v_rms / EFFECTIVE_SENSITIVITY
    if i_rms < NOISE_FLOOR_A:
        i_rms = 0.0

    return i_rms

#Reading Voltage RMS
def read_volt_rms():
    samples = []
    for _ in range(SAMPLES):
        samples.append(volt_adc.read_u16()>>4)
        time.sleep_us(SAMPLE_INTERVAL_US)

    mean = sum(samples) / len(samples)
    sq_sum = sum((s - mean) ** 2 for s in samples)
    rms_raw = math.sqrt(sq_sum / len(samples))
    rms_volts_adc = (rms_raw / 4095) * 3.3
    print("raw min:", min(samples), "raw max:", max(samples), "raw mean:", mean)

    return rms_volts_adc * CALIBRATION


# --- Main ---
connect_wifi(WIFI_SSID, WIFI_PASSWORD)

time.sleep_ms(100)

i2c = SoftI2C(sda=Pin(sda_pin), scl=Pin(scl_pin), freq=50000)
lcd_address = detect_lcd_address(i2c)
print(f"I2C Channel: {i2c}")
print(f"Address: {hex(lcd_address)} | SDA: {sda_pin} | SCL: {scl_pin}")

time.sleep_ms(100)

lcd = I2cLcd(i2c, lcd_address, LCD_ROWS, LCD_COLS)
lcd.backlight_on()
lcd.clear()
lcd.move_to(0, 0)
lcd.putstr("Initializing...")
lcd.move_to(0, 1)
lcd.putstr("Energy Meter")
time.sleep(2)

lcd.clear()
lcd.move_to(0, 0)
lcd.putstr("Status:")
lcd.move_to(0, 1)
lcd.putstr("Starting...")
time.sleep(1)

print("Starting energy monitor...")
last_time = time.ticks_ms()


last_telegram_time = time.ticks_ms()   

while True:
    voltage = read_volt_rms()
    current = read_ac_current_rms()
    
    power_watts = voltage * current * POWER_FACTOR

    now = time.ticks_ms()
    elapsed_hours = (time.ticks_diff(now, last_time) )/ (1000 * 3600)
    last_time = now

    total_energy_wh += power_watts * elapsed_hours
    total_energy_kwh = total_energy_wh / 1000.0

    print("V: {:.2f} V | I: {:.2f} A | P: {:.2f} W | Energy: {:.2f} kWh".format(
        voltage, current, power_watts, total_energy_kwh))
    
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("V:{:5.1f} I:{:4.2f}A".format(voltage, current))
    lcd.move_to(0, 1)
    lcd.putstr("P:{:5.1f}W E:{:5.3f}".format(power_watts, total_energy_kwh))
    
    #Sending the readings through Telegram
    if time.ticks_diff(now, last_telegram_time) >= TELEGRAM_SEND_INTERVAL_SEC * 1000:
        message = (
            "Energy Monitor Update\n"
            "Voltage: {:.2f} V\n"
            "Current: {:.2f} A\n"
            "Power: {:.2f} W\n"
            "Energy: {:.3f} kWh"
        ).format(voltage, current, power_watts, total_energy_kwh)
        send_telegram_message(message)
        print("msg sent")
        last_telegram_time = now

    time.sleep(1)
