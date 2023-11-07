import unittest

from src.bpod import Bpod, find_bpod_ports

bpod_port = next(find_bpod_ports(), None)


@unittest.skipIf(bpod_port is None, 'No Bpod device found')
class TestSerial(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._bpod = Bpod()

    def test_datatypes(self):
        pass

    def test_serial_number(self):
        sn = self._bpod.info.serial_number
        my_bpod = Bpod(serial_number=sn)
        assert my_bpod == self._bpod

    @classmethod
    def tearDownClass(cls) -> None:
        cls._bpod.close()
