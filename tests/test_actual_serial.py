import unittest
from src.bpod import Bpod

bpod_port = next(Bpod.find(), None)


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
