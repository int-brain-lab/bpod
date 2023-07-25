import serial
import logging

logging.basicConfig(
    format="%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.DEBUG,
)
log = logging.getLogger(__name__)


class Bpod(serial.Serial):
    """Class for interfacing a Bpod Finite State Machine.

    The Bpod class extends the :class:`serial.Serial` class.
    """

    def __init__(self, port=None, connect_bpod: bool = True, **kwargs):
        super().__init__(**kwargs)
        if not port:
            return
        super().setPort(port)
        if connect_bpod:
            self.open()
