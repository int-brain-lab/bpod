import unittest
import logging

from src.bpod import Bpod

logging.basicConfig(level=logging.DEBUG)


class TestBpod(unittest.TestCase):
    def test_unconnected(self):
        bpod = Bpod()
        assert bpod.is_open is False

    def test_singleton(self):
        bpod1 = Bpod()
        bpod2 = Bpod()
        bpod3 = Bpod("COM3", connect=False)
        bpod4 = Bpod("COM4", connect=False)
        bpod5 = Bpod(port="COM4", connect=False)
        assert bpod1 is bpod2
        assert bpod1 is not bpod3
        assert bpod3 is not bpod4
        assert bpod4 is bpod5

    def test_set_port(self):
        bpod = Bpod()
        self.assertRaises(Exception, bpod.setPort)
