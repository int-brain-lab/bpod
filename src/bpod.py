from __future__ import annotations
from typing import NoReturn, Type, NamedTuple
import logging
import threading

# from box import Box

from serial.threaded import ReaderThread, Protocol
import numpy as np
import serial

logging.basicConfig(
    format="%(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.DEBUG,
)
log = logging.getLogger(__name__)


class SerialReaderProtocolRaw(Protocol):
    def connection_made(self, transport):
        """Called when reader thread is started"""
        print("Threaded serial reader started - ready to receive data...")

    def data_received(self, data):
        """Called with snippets received from the serial port"""
        print(data.decode())

    def connection_lost(self, exc):
        log.info(exc)


class BpodException(Exception):
    pass


class Bpod(serial.Serial):
    """Class for interfacing a Bpod Finite State Machine.

    The Bpod class extends the :class:`serial.Serial` class.
    """

    _instances: dict = dict()
    _lock = threading.Lock()

    def __new__(cls, port: str | None = None, **kwargs) -> Bpod:
        if port is not None and not isinstance(port, np.compat.basestring):
            raise ValueError("'port' must be None or a string")
        with cls._lock:
            instance = Bpod._instances.get(port, None)
            if instance is None:
                log.debug(
                    "Creating new Bpod instance for port '{}'".format(port or "None")
                )
                instance = super().__new__(cls)
                Bpod._instances[port] = instance
            else:
                log.debug(
                    "Using existing Bpod instance on port '{}'".format(port or "None")
                )
            return instance

    def __init__(self, port: str | None = None, connect: bool = True, **kwargs) -> None:
        if "baudrate" not in kwargs:
            kwargs["baudrate"] = 1312500
        super().__init__(**kwargs)
        super().setPort(port)

        self.version: dict = dict()
        self.hardware: dict = dict()
        self.inputs = None
        self.outputs = None
        self.modules: Modules = Type[Modules]
        self._reader = ReaderThread(self, SerialReaderProtocolRaw)

        if port is not None and connect is True:
            self.open()

    def __del__(self) -> None:
        self.close()
        with self._lock:
            if self._port in Bpod._instances:
                log.debug("Deleting instance on port '{}'".format(self.port or "None"))
                Bpod._instances.pop(self._port)

    def setPort(self, port) -> NoReturn:
        """Overwrite setPort() method of parent class."""
        raise BpodException("Port cannot be changed after instantiation.")

    def open(self) -> None:
        """Open serial connection and connect to Bpod Finite State Machine.

        Raises
        ------
        BpodException
            Handshake failed: The Bpod did not acknowledge our request.
        """
        log.info("Connecting to Bpod device ...")
        super().open()
        log.debug("Serial port '{}' opened.".format(self.portstr))

        if not self.handshake():
            raise BpodException("Handshake failed")
        log.debug("Handshake successful")

        # get Bpod version & machine type
        self.version["major"], self.hardware["machine_type"] = self.query(
            "F", 4, np.uint16
        )
        self.version["minor"] = (
            self.query("f", 2, np.uint16)
            if self.version["major"] > 22
            else np.uint16(0)
        )
        log.info("Firmware v%d.%d", self.version["major"], self.version["minor"])

        log.debug("Obtaining hardware configuration ...")
        hw, s = self.query_chunks(b"H", 3, 9)
        self.hardware.update(
            dict(
                zip(["max_states", "timer_period"], np.frombuffer(hw, np.uint16, 2, 0))
            )
        )
        self.hardware.update(
            dict(
                zip(
                    [
                        "max_serial_events",
                        "n_global_timers",
                        "n_global_counters",
                        "n_conditions",
                        "n_conditions",
                        "n_inputs",
                    ],
                    np.frombuffer(hw, np.uint8, 6, 3),
                )
            )
        )
        self.hardware["input_description_array"] = hw[9 : 9 + self.hardware["n_inputs"]]
        self.hardware["n_outputs"] = hw[9 + self.hardware["n_inputs"]]
        self.hardware["output_description_array"] = hw[-self.hardware["n_outputs"] :]

        log.debug("Configuring I/O ports")

        def collect_channels(
            description: str, dictionary: dict, channel_class
        ) -> NamedTuple[Channel]:
            channels = []
            types = []
            for idx in range(len(description)):
                io_key = description[idx : idx + 1]
                if io_key in dictionary.keys():
                    n = description[:idx].count(io_key) + 1
                    name = "{}{}".format(dictionary[io_key], n)
                    channels.append(channel_class(self, name, io_key, idx))
                    types.append((name, channel_class))
            tmp = NamedTuple(channel_class.__name__, types)
            return tmp(*channels)

        io_dict_input = {b"B": "BNC", b"V": "Valve", b"P": "Port", b"W": "Wire"}
        io_dict_output = {b"B": "BNC", b"V": "Valve", b"P": "PWM", b"W": "Wire"}
        self.inputs = collect_channels(
            self.hardware["input_description_array"], io_dict_input, Input
        )
        self.outputs = collect_channels(
            self.hardware["output_description_array"], io_dict_output, Output
        )

        # log.debug("Configuring modules")
        # self.modules = Modules(self)

    def close(self):
        if not self.is_open:
            return
        log.debug("Disconnecting state machine.")
        self.write(b"Z")
        super().close()
        log.debug("Serial port '{}' closed.".format(self.portstr))

    def handshake(self) -> bool:
        """Try to perform a handshake with a Bpod Finite State Machine.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        return self.query(b"6") == b"5"

    def write(self, data: any) -> int:
        """Read data from the Bpod.

        Parameters
        ----------
        data : any
            Data to be written to the Bpod.

        Returns
        -------
        int
            Number of bytes written to the Bpod.
        """
        return super().write(self.to_bytes(data))

    def read(self, n_bytes: int = 1, dtype: type = bytes) -> bytes | np.ndarray:
        """Read data from the Bpod.

        Parameters
        ----------
        n_bytes : int, default: 1
            Number of bytes to receive from the Bpod.
        dtype : type, default: bytes
            Desired type of the returned data - by default: bytes. Any other data-type
            will be returned as a NumPy array.

        Returns
        -------
        bytes | np.ndarray
            Data returned by the Bpod. By default, the response is formatted as a
            bytestring. You can alternatively request a NumPy array by specifying the
            dtype argument (see above).
        """
        data = super().read(n_bytes)
        return data if dtype is bytes else np.frombuffer(data, dtype)

    def query(
        self, query: any, n_bytes: int = 1, dtype: type = bytes
    ) -> bytes | np.ndarray:
        """Query data from the Bpod.

        Parameters
        ----------
        query : any
            Query to be sent to the Bpod.
        n_bytes : int, default: 1
            Number of bytes to receive from the Bpod.
        dtype : type, default: bytes
            Desired type of the returned data - by default: bytes. Any other data-type
            will be returned as a NumPy array.

        Returns
        -------
        bytes | np.ndarray
            Data returned by the Bpod. By default, the response is formatted as a
            bytestring. You can alternatively request a NumPy array by specifying the
            dtype argument (see above).
        """
        self.write(query)
        return self.read(n_bytes, dtype)

    def query_chunks(self, query: any, n_chunks: int, first_len: int) -> (bytes, list):
        """Receive multiple chunks of data from Bpod.

        The last byte of each chunk (except the last one) determines the length of the
        next chunk.

        Parameters
        ----------
        query : any
            Query to be sent to the Bpod.
        n_chunks : int
            Number of chunks to read.
        first_len : int
            Length of first chunk.

        Returns
        -------
        chunks : bytes
            All chunks of data received from the Bpod, concatenated to a single
            bytestring.
        slices : slice
            Slices for recovering individual data chunks from the bytestring.
        """
        self.write(query)
        out = b""
        slices = [slice(0, first_len)]
        n = first_len
        for i in range(n_chunks):
            out = b"".join([out, self.read(n)])
            if i < (n_chunks - 1):
                n = out[slices[i].stop - 1] + (i != n_chunks - 2)
                slices.append(slice(slices[i].stop, slices[i].stop + n))
        return out[: slices[-1].stop], slices

    @staticmethod
    def to_bytes(data: any) -> bytes:
        """Convert data to bytestring.

        This method extends :meth:`serial.to_bytes` with support for NumPy types,
        strings (interpreted as utf-8) and lists.

        Parameters
        ----------
        data : any
            Data to be converted to bytestring.

        Returns
        -------
        bytes
            Data converted to bytestring.
        """
        match data:
            case np.ndarray() | np.generic():
                data = data.tobytes()
            case int():
                data = np.uint8(data)
            case str():
                data = data.encode("utf-8")
            case list():
                data = b"".join([Bpod.to_bytes(item) for item in data])
            case _:
                data = serial.to_bytes(data)
        return data


class Channel(object):
    def __init__(self, bpod: Bpod, name: str, io_type: bytes, index: int):
        self.name = name
        self.io_type = io_type
        self.index = index
        self._query = bpod.query
        self._write = bpod.write

    def __str__(self):
        return self.name


class Input(Channel):
    def read(self) -> bool:
        return self._query(["I", self.index], 1) == b"\x01"

    def override(self, state: bool) -> None:
        self._write(["V", state])

    def enable(self, state: bool) -> None:
        pass


class Output(Channel):
    def override(self, state: bool | np.uint8) -> None:
        if self.io_type in [b"D", b"B", b"W"]:
            state = state > 0
        self._write(["O", self.index, state])


class Modules(object):
    def __init__(self, bpod: Bpod):
        self._bpod = bpod
        self.update_modules()

    def update_modules(self):
        pass
        # self._bpod.write(b"M")
        # modules = [None] * self._bpod.hardware["output_description_array"].count(b"U")
        # for i in range(len(modules)):
        #     if self._bpod.read() == bytes([1]):
        #         continue


class Module(object):
    pass
    # def __init__(self, bpod: Bpod, port: int, **kwargs):
    #     super().__init_subclass__(**kwargs)
    #     self._bpod = bpod
    #     self.port = port
    #     self.firmware_version = bpod.read(4, np.uint32)[0]
    #     self.name = bpod.read(int(bpod.read())).decode("utf-8")
    #     while bpod.read() == b"\x01":
    #         match bpod.read():
    #             case b"#":
    #                 self."number_of_events"] = self._bpod.read(1, np.uint8)[0]
    #             case b"E":
    #                 for event_index in range(self._bpod.read(1, np.uint8)[0]):
    #                     length_of_event_name = self._bpod.read(1, np.uint8)[0]
    #                     module["events"]["index"] = event_index
    #                     module["events"]["name"] = self._bpod.read(
    #                         length_of_event_name, str
    #                     )[0]
    #         modules[i] = module
    #     self._children = modules
