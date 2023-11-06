from bpod import SerialSingleton
from serial import SerialTimeoutException
from serial.tools.list_ports import comports
import logging

logger = logging.getLogger(__name__)


class Frame2TTL(SerialSingleton):
    def __init__(self, port: str, *args, **kwargs) -> None:
        if self._instantiated:
            return

        # override default arguments of super-class
        if "baudrate" not in kwargs:
            kwargs["baudrate"] = 115200
        if "timeout" not in kwargs:
            kwargs["timeout"] = 0.5
        if "write_timeout" not in kwargs:
            kwargs["write_timeout"] = 0.5

        super().__init__(*args, **kwargs)
        self.port = port
        super().open()

        # get more information on USB device
        port_info = next((p for p in comports() if p.device == self.portstr), None)
        if not port_info or not port_info.vid:
            raise IOError(f"Device on {self.portstr} is not a Frame2TTL")

        # detect SAMD21 Mini Breakout (Frame2TTL v1)
        is_samd21mini = port_info.vid == 0x1B4F and port_info.pid in [0x8D21, 0x0D21]
        if is_samd21mini and port_info.pid == 0x0D21:
            raise IOError(
                f"SAMD21 Mini Breakout on {self.portstr} is in bootloader "
                f"mode. Unplugging and replugging the device should "
                f"alleviate the issue. If not, try reflashing the Frame2TTL "
                f"firmware."
            )

        # try to connect and identify Frame2TTL
        try:
            self.write(b"C")
        except SerialTimeoutException as e:
            if is_samd21mini:
                raise IOError(
                    f"Writing to {self.portstr} timed out. This is a known"
                    f"problem with the SAMD21 mini breakout used by "
                    f"Frame2TTL v1. Unplugging and replugging the device is"
                    f"currently the only known fix."
                ) from e
            else:
                raise e
        finally:
            if self.read() != bytes([218]):
                raise IOError(f"Device on {self.portstr} is not a Frame2TTL")

        # get hardware version
        if is_samd21mini:
            self.hw_version = 1
        else:
            self.write("#")
            self.hw_version = self.read()


a = Frame2TTL("/dev/ttyACM0")
