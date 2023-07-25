import unittest
import logging

from src.bpod import Bpod

logging.basicConfig(level=logging.DEBUG)


class TestUnconnected(unittest.TestCase):
    def test_unconnected(self):
        bpod = Bpod()
        assert bpod.is_open is False
        bpod.close()
