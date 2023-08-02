import unittest
from serial import Serial, SerialException
from serial.tools import list_ports
from bpod import Bpod

bpod_port = ''
for port in list_ports.comports():
    try:
        p = Serial(port.device, timeout=0.2)
        if p.read(1) == bytes([222]):
            p.close()
            bpod_port = port.device
            break
        p.close()
    except SerialException:
        pass


@unittest.skipUnless(len(bpod_port) > 0, "No Bpod device found")
class TestSerial(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._bpod = Bpod(bpod_port)

    def test_datatypes(self):
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        cls._bpod.close()