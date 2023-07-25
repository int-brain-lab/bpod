from __future__ import annotations
from typing import Literal
import logging

import numpy as np
import serial

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

    version: dict = dict()

    hardware: dict = dict()
    """Dictionary containing information about the hardware."""

    input: dict = dict()
    output: dict = dict()

    def __init__(self, port=None, connect_bpod: bool = True, **kwargs):
        super().__init__(**kwargs)
        super().setPort(port)
        if port and connect_bpod:
            self.open()

    def open(self) -> None:
        """Open serial connection and connect to Bpod Finite State Machine.

        Raises
        ------
        Exception
            Handshake failed: The Bpod did not acknowledge our request.
        """
        super().open()
        log.debug('Serial port "{}" opened.'.format(self.portstr))

        log.info("Connecting to Bpod ...")
        if not self.handshake():
            raise Exception("Handshake failed")
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

        log.debug("Configuring I/O ...")
        self.input = self._create_io("input")
        self.output = self._create_io("output")

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

    def query_chunks(
        self, query: any, n_chunks: int, first_len: int, n_preallocate: int = 128
    ) -> (bytes, list):
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
        n_preallocate : int, default: 128
            Number of bytes to preallocate.

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

    def _create_io(self, direction: Literal["input", "output"]) -> dict:
        if direction == "input":
            description_array = self.hardware["input_description_array"]
            constructor = self.Input
        elif direction == "output":
            description_array = self.hardware["output_description_array"]
            constructor = self.Output
        else:
            raise Exception("parameter direction must be either 'input' or 'output'.")

        out = dict()
        for i in range(len(description_array)):
            io_type = description_array[i : i + 1]
            match io_type:
                case b"B":
                    name = "BNC"
                case b"V":
                    name = "Valve"
                case b"P":
                    name = "Port"
                case _:
                    continue
            name = "{}{}".format(name, description_array[:i].count(io_type) + 1)
            out[name] = constructor(self, i, io_type, name)
        return out

    class _IO:
        def __init__(self, parent: Bpod, index: int, io_type: bytes, name: str):
            if index == 0:
                raise Exception("Bpod I/O uses one-based indexing.")
            self._io_type = io_type
            self.index = index
            self.name = name
            self._query = parent.query
            self._write = parent.write

    class Input(_IO):
        def read(self) -> bool:
            return self._query(("I", self.index), 1) == b"\x01"

        def override(self, state: bool) -> None:
            self._write(("V", state))

        def enable(self, state: bool) -> None:
            pass

    class Output(_IO):
        def override(self, state: bool | np.uint8) -> None:
            if self._io_type == b"D" or b"B" or b"W":
                state = state > 0
            self._write(("O", self.index, state))
