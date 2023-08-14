import unittest
from src.bpod import Bpod, find_bpod_ports

bpod_port = next(find_bpod_ports(), None)


@unittest.skipIf(bpod_port is None, "No Bpod device found")
class TestSerial(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._bpod = Bpod()

    def test_datatypes(self):
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        cls._bpod.close()
