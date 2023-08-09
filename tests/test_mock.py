# import unittest
# from unittest.mock import patch, Mock
# from bpod import Bpod
#
#
# class TestBpodInit(unittest.TestCase):
#     @patch("bpod.Bpod._instances", {})
#     def setUp(self):
#         self.mock_serial = Mock()
#         self.mock_serial.return_value = self.mock_serial
#         self.mock_serial_instance = self.mock_serial.return_value
#         self.mock_serial_instance.port = None  # Set the port to None initially
#
#     def test_init_with_port_and_connect(self):
#         with patch(
#             "serial.Serial",
#             autospec=True,
#             return_value=self.mock_serial,
#         ):
#             bpod_instance = Bpod(port="COM3")
#
#         self.mock_serial.assert_called_once_with(
#             baudrate=1312500, timeout=None, port="COM3"
#         )
#         self.assertIs(bpod_instance._reader.protocol, "SerialReaderProtocolRaw")
#         self.assertTrue(bpod_instance._instantiated)
#         self.assertEqual(Bpod._instances["COM3"], bpod_instance)
#
#     # Add more test cases as needed for different scenarios (e.g., port=None, connect=False)
#
#
# if __name__ == "__main__":
#     unittest.main()
