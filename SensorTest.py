"""Read an Ohmite FSR01 every 200 ms on a Pico 2 W running MicroPython.

Voltage-divider wiring:
    3V3(OUT) -- FSR01 --+-- GP27 (ADC1)
                       |
                     10 kohm
                       |
                      GND

Use 3.3 V, never 5 V, for this divider. Readings are not calibrated force.
Save this file as main.py ON THE PICO to start sending readings at power-on.
Run HeatMapInterp.py on the computer. The machine module exists on the Pico,
so a desktop Python interpreter may flag its import as unresolved.
"""

from machine import ADC, Pin
import time


ADC_PIN = 27  # GP27 matches the sensor wiring used for this test.
INTERVAL_MS = 200
REFERENCE_VOLTAGE = 3.3

sensor = ADC(Pin(ADC_PIN))

try:
    while True:
        raw = sensor.read_u16()
        voltage = raw * REFERENCE_VOLTAGE / 65535
        print("Raw: {:5d} | Voltage: {:.3f} V".format(raw, voltage))
        time.sleep(INTERVAL_MS / 1000)
except KeyboardInterrupt:
    print("Sensor test stopped.")
