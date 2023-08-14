from __future__ import annotations

import ctypes
from abc import abstractmethod
from collections.abc import Iterator
from typing import NamedTuple, Any, Sequence, Union, Optional, overload, TYPE_CHECKING
import logging
import threading
from struct import pack_into, unpack, calcsize

import serial
from serial.serialutil import to_bytes  # type: ignore
from serial.threaded import ReaderThread, Protocol
from serial.tools import list_ports
import numpy as np


if TYPE_CHECKING:
    from _typeshed import ReadableBuffer  # noqa:401

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

    The Bpod class extends :class:`serial.Serial`.

    Parameters
    ----------
    port : str, optional
        The serial port for the Bpod device, or None to automatically detect a Bpod.
    connect : bool, default: True
        Whether to connect to the Bpod device. If True and 'port' is None, an
        attempt will be made to automatically find and connect to a Bpod device.
    **kwargs
        Additional keyword arguments passed to :class:`serial.Serial`.

    Examples
    --------

    * Try to automatically find a Bpod device and connect to it.

        .. code-block:: python

            my_bpod = Bpod()

    * Connect to a Bpod device on COM3

        .. code-block:: python

            my_bpod = Bpod('COM3')

    * Instantiate a Bpod object for a device on COM3 but only connect to it later.

        .. code-block:: python

            my_bpod = Bpod(port = "COM3", connect = False)
            # (do other things)
            my_bpod.open()
    """

    _instances: dict = dict()
    _instantiated = False
    _lock: threading.Lock = threading.Lock()

    class _Info(NamedTuple):
        firmware_version: tuple[int, int]
        machine_type: int
        machine_type_string: str
        pcb_revision: int
        max_states: int
        timer_period: int
        max_serial_events: int
        max_bytes_per_serial_message: int
        n_global_timers: int
        n_global_counters: int
        n_conditions: int
        n_inputs: int
        input_description_array: bytes
        n_outputs: int
        output_description_array: bytes

    def __new__(
        cls, port: Optional[str] = None, connect: Optional[bool] = True, **kwargs
    ) -> Bpod:
        """
        Create or retrieve a singleton instance of the Bpod class.

        This method implements a singleton pattern for the Bpod class, ensuring that
        only one instance is created for a given port. If an instance already exists
        for the specified port, that instance is returned.

        Parameters
        ----------
        port : str, optional
            The serial port for the Bpod device, or None to automatically detect a Bpod.
        connect : bool, optional
            Whether to connect to the Bpod device. If True and 'port' is None, an
            attempt will be made to automatically find and connect to a Bpod device.
        **kwargs
            Additional keyword arguments passed to serial.Serial.

        Returns
        -------
        Bpod
            A singleton instance of the Bpod class.

        Raises
        ------
        ValueError
            If 'port' is not a string and is not None.

        Notes
        -----
        The singleton instances are managed by a class-level lock and dictionary.
        Automatic Bpod detection relies on the find method.

        Example
        -------
        To create or retrieve a Bpod instance on a specific port:

        .. code-block:: python
            bpod_instance = Bpod(port='COM3')

        To automatically detect and create or retrieve a Bpod instance:

        .. code-block:: python
            bpod_instance = Bpod()
        """
        if not isinstance(port, str) and port is not None:
            raise ValueError("Parameter 'port' must be a string or None.")

        # try to automagically find a Bpod device
        if port is None and connect is True:
            port = next(iter(Bpod._instances.keys()), next(find_bpod_ports(), None))

        # implement singleton
        with cls._lock:
            instance = Bpod._instances.get(port, None)
            if instance is None:
                log.debug(f"Creating new Bpod instance on {port}")
                instance = super().__new__(cls)
                Bpod._instances[port] = instance
            else:
                log.debug(f"Using existing Bpod instance on {port}")
            return instance

    def __init__(
        self, port: Optional[str] = None, connect: Optional[bool] = True, **kwargs
    ) -> None:
        """
        Initialize a Bpod instance.

        This method initializes a Bpod instance, allowing communication with a Bpod
        device over a specified serial port.

        Parameters
        ----------
        port : str, optional
            The serial port for the Bpod device. If None and 'connect' is True, an
            attempt will be made to automatically detect and use a Bpod port.
        connect : bool, optional
            Whether to establish a connection to the Bpod device. If True and 'port' is
            None, automatic port detection will be attempted.
        **kwargs
            Additional keyword arguments to be passed to the constructor of
            serial.Serial.

        Notes
        -----
        -   If the Bpod instance is already instantiated, the method returns without
            further action.
        -   If 'port' is 'None' and 'connect' is True the former value may be
            overridden based on existing instances
        """
        if self._instantiated:
            return

        # override port kwarg when using automatic port discovery (see __new__)
        if port is None and connect is True:
            port = next((k for (k, v) in self._instances.items() if v is self), None)

        # initiate super class
        if "baudrate" not in kwargs:
            kwargs["baudrate"] = 1312500
        super().__init__(**kwargs)
        self.port = port

        self.info: Bpod._Info | None = None
        self.inputs = None
        self.outputs = None
        self._reader: ReaderThread = ReaderThread(self, SerialReaderProtocolRaw)
        self._instantiated = True

        if port is not None and connect is True:
            self.open()

    def __del__(self) -> None:
        self.close()
        with self._lock:
            if self.port in Bpod._instances:
                log.debug(f"Deleting instance on {self.port}")
                Bpod._instances.pop(self.port)

    def __repr__(self):
        return f"Bpod(port={self.port})"

    @property
    def port(self) -> Union[str, None]:
        """
        Get the communication port used for the Bpod device.

        Returns
        -------
        str
            The serial port (e.g., 'COM3', '/dev/ttyUSB0') used by the Bpod device.
        """
        return super().port

    @port.setter
    def port(self, port):
        """
        Set the communication port for the Bpod device.

        This setter allows changing the communication port before the object is
        instantiated. Once the object is instantiated, attempting to change the port
        will raise a BpodException.

        Parameters
        ----------
        port : str
            The new communication port to be set (e.g., 'COM3', '/dev/ttyUSB0').

        Raises
        ------
        BpodException
            If an attempt is made to change the port after the object has been
            instantiated.
        """
        if not self._instantiated:
            super(type(self), type(self)).port.fset(self, port)
            return
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
        log.debug(f"Serial port {self.port} opened")

        # try to perform handshake
        if not self.handshake():
            raise BpodException("Handshake failed")
        log.debug("Handshake successful")

        # get firmware version, machine type & PCB revision
        v_major, machine_type = self.query(b"F", "<2H")
        version = (v_major, self.query(b"f", "<H")[0] if v_major > 22 else 0)
        machine_str = {1: "v0.5", 2: "r07+", 3: "r2.0-2.5", 4: "2+ r1.0"}[machine_type]
        pcb_rev = self.query(b"v", "<B")[0] if v_major > 22 else None

        # log hardware information
        log.info("Bpod Finite State Machine " + machine_str)
        log.info("Circuit board revision {pcb_rev}") if pcb_rev else None
        log.info("Firmware version {}.{}".format(*version))

        # get hardware description
        info: list[Any] = [version, machine_type, machine_str, pcb_rev]
        if v_major > 22:
            info.extend(self.query(b"H", "<2H6B"))
        else:
            info.extend(self.query(b"H", "<2H5B"))
            info.insert(-4, 3)  # max bytes per serial msg always = 3
        info.extend(self.read(f"<{info[-1]}s1B"))
        self.info = Bpod._Info(*info, *self.read(f"<{info[-1]}s"))

        def collect_channels(description: bytes, dictionary: dict, channel_cls: type):
            """
            Generate a collection of channels based on the given description array and
            dictionary.

            This method takes a channel description array (as returned by the Bpod), a
            dictionary mapping keys to names, and a channel class. It generates named
            tuple instances and sets them as attributes on the current Bpod instance.
            """
            channels = []
            types = []

            for idx in range(len(description)):
                io_key = description[idx : idx + 1]
                if bytes(io_key) in dictionary.keys():
                    n = description[:idx].count(io_key) + 1
                    name = f"{dictionary[io_key]}{n}"
                    channels.append(channel_cls(self, name, io_key, idx))
                    types.append((name, channel_cls))

            cls_name = f"{channel_cls.__name__.lower()}s"
            setattr(self, cls_name, NamedTuple(cls_name, types)._make(channels))

        log.debug("Configuring I/O ports")
        input_dict = {b"B": "BNC", b"V": "Valve", b"P": "Port", b"W": "Wire"}
        output_dict = {b"B": "BNC", b"V": "Valve", b"P": "PWM", b"W": "Wire"}
        collect_channels(self.info.input_description_array, input_dict, Input)
        collect_channels(self.info.output_description_array, output_dict, Output)

        # log.debug("Configuring modules")
        # self.modules = Modules(self)

    def close(self):
        """
        Disconnect the state machine and close the serial connection.

        Example
        -------
            .. code-block:: python
                :emphasize-lines: 3

                my_bpod = Bpod("COM3")
                # [Perform operations with the state machine]
                my_bpod.close()
        """
        if not self.is_open:
            return
        log.debug("Disconnecting state machine")
        self.write(b"Z")
        super().close()
        log.debug(f"Serial port {self.port} closed")

    def handshake(self) -> bool:
        """
        Try to perform handshake with Bpod device.

        Returns
        -------
        bool
            True if successful, False otherwise.

        Notes
        -----
        This will reset the state machine's session clock and flush the serial port.
        """
        success = self.query(b"6") == b"5"
        self.reset_input_buffer()
        return success

    def write(self, data: Union[tuple[Sequence[Any], str], Any]) -> Union[int, None]:
        """Write data to the Bpod.

        Parameters
        ----------
        data : any
            Data to be written to the Bpod.
            See https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        int or None
            Number of bytes written to the Bpod.
        """
        if isinstance(data, tuple()):
            size = calcsize(data[1])
            buff = ctypes.create_string_buffer(size)
            pack_into(data[1], buff, 0, *data[0])
            return super().write(buff)
        else:
            return super().write(self.to_bytes(data))

    @overload
    def read(self, data_specifier: str) -> tuple[Any, ...]:
        ...

    @overload
    def read(self, data_specifier: int = 1) -> bytes:
        ...

    def read(self, data_specifier=1):
        """
        Read data from the Bpod.

        Parameters
        ----------
        data_specifier : int or str, default: 1
            The number of bytes to receive from the Bpod, or a format string for
            unpacking.

            When providing an integer, the specified number of bytes will be returned
            as a bytestring. When providing a `format string`_, the data will be
            unpacked into a tuple accordingly. Format strings follow the conventions of
            the :mod:`struct` module.

            .. _format string:
                https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        bytes or tuple[Any]
            Data returned by the Bpod. By default, data is formatted as a bytestring.
            Alternatively, when provided with a format string, data will be unpacked
            into a tuple according to the specified format string.

        Examples
        --------

        Receive 4 bytes of data from a Bpod device - first interpreted as a bytestring,
        then as a tuple of two unsigned short integers:

        .. code-block:: python
            :emphasize-lines: 3,4,7,8

            my_bpod.write(b"F")
            1
            my_bpod.read(4)
            b'\\x16\\x00\\x03\\x00'
            my_bpod.write(b"F")
            1
            my_bpod.read('2H')
            (22, 3)
        """
        if isinstance(data_specifier, str):
            n_bytes = calcsize(data_specifier)
            return unpack(data_specifier, super().read(n_bytes))
        else:
            return super().read(data_specifier)

    @overload
    def query(
        self, query: Union[bytes, Sequence[Any]], data_specifier: int = 1
    ) -> bytes:
        ...

    @overload
    def query(
        self, query: Union[bytes, Sequence[Any]], data_specifier: str
    ) -> tuple[Any, ...]:
        ...

    def query(self, query, data_specifier=1):
        """Query data from the Bpod.

        This method is a combination of :py:meth:`write` and :py:meth:`read`.

        Parameters
        ----------
        query : any
            Query to be sent to the Bpod.
        data_specifier : int or str, default: 1
            The number of bytes to receive from the Bpod, or a format string for
            unpacking.

            When providing an integer, the specified number of bytes will be returned
            as a bytestring. When providing a `format string`_, the data will be
            unpacked into a tuple accordingly. Format strings follow the conventions of
            the :py:mod:`struct` module.

            .. _format string:
                https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        bytes or tuple[Any]
            Data returned by the Bpod. By default, data is formatted as a bytestring.
            Alternatively, when provided with a format string, data will be unpacked
            into a tuple according to the specified format string.


        Examples
        --------

        Query 4 bytes of data from a Bpod device - first interpreted as a bytestring,
        then as a tuple of two unsigned short integers:

        .. code-block:: python
            :emphasize-lines: 2

            my_bpod.query(b"F", 4)
            b'\\x16\\x00\\x03\\x00'
            my_bpod.query(b"F", '2H')
            (22, 3)
        """
        self.write(query)
        return self.read(data_specifier)

    @staticmethod
    def to_bytes(data: Any) -> bytes:
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
                data = data.to_bytes(1, "little")
            case str():
                data = data.encode("utf-8")
            case list():
                data = b"".join([Bpod.to_bytes(item) for item in data])
            case _:
                data = to_bytes(data)
        return data

    def update_modules(self):
        pass
        # self.write(b"M")
        # modules = []
        # for i in range(len(modules)):
        #     if self.read() == bytes([1]):
        #         continue
        #     firmware_version = self.read(4, np.uint32)[0]
        #     name = self.read(int(self.read())).decode("utf-8")
        #     port = i + 1
        #     m = Module()
        #     while self.read() == b"\x01":
        #         match self.read():
        #             case b"#":
        #                 number_of_events = self.read(1, np.uint8)[0]
        #             case b"E":
        #                 for event_index in range(self.read(1, np.uint8)[0]):
        #                     l_event_name = self.read(1, np.uint8)[0]
        #                     module["events"]["index"] = event_index
        #                     module["events"]["name"] = self.read(l_event_name, str)[0]
        #         modules[i] = module
        #     self._children = modules


class Channel(object):
    @abstractmethod
    def __init__(self, bpod: Bpod, name: str, io_type: bytes, index: int):
        """
        Abstract base class representing a channel on the Bpod device.

        Parameters
        ----------
        bpod : Bpod
            The Bpod instance associated with the channel.
        name : str
            The name of the channel.
        io_type : bytes
            The I/O type of the channel (e.g., 'B', 'V', 'P').
        index : int
            The index of the channel.
        """
        self.name = name
        self.io_type = io_type
        self.index = index
        self._query = bpod.query
        self._write = bpod.write

    def __repr__(self):
        return self.__class__.__name__ + "()"


class Input(Channel):
    def __init__(self, *args, **kwargs):
        """
        Input channel class representing a digital input channel.

        Parameters
        ----------
        *args, **kwargs
            Arguments to be passed to the base class constructor.
        """
        super().__init__(*args, **kwargs)

    def read(self) -> bool:
        """
        Read the state of the input channel.

        Returns
        -------
        bool
            True if the input channel is active, False otherwise.
        """
        return self._query(["I", self.index], 1) == b"\x01"

    def override(self, state: bool) -> None:
        """
        Override the state of the input channel.

        Parameters
        ----------
        state : bool
            The state to set for the input channel.
        """
        self._write(["V", state])

    def enable(self, state: bool) -> None:
        """
        Enable or disable the input channel.

        Parameters
        ----------
        state : bool
            True to enable the input channel, False to disable.
        """
        pass


class Output(Channel):
    def __init__(self, *args, **kwargs):
        """
        Output channel class representing a digital output channel.

        Parameters
        ----------
        *args, **kwargs
            Arguments to be passed to the base class constructor.
        """
        super().__init__(*args, **kwargs)

    def override(self, state: Union[bool, int]) -> None:
        """
        Override the state of the output channel.

        Parameters
        ----------
        state : Union[bool, int]
            The state to set for the output channel. For binary I/O types, provide a
            bool. For pulse width modulation (PWM) I/O types, provide an int (0-255).
        """
        if isinstance(state, int) and self.io_type in [b"D", b"B", b"W"]:
            state = state > 0
        self._write(["O", self.index, state.to_bytes(1, "little")])


class Module(object):
    pass


def find_bpod_ports() -> Iterator[str]:
    """Discover serial ports used by Bpod devices.

    This method scans through the list of available serial ports and identifies ports
    that are in use by a Bpod device. It does so by briefly opening each port and
    checking for a specific byte pattern (byte 222). Ports matching this pattern are
    yielded.

    Yields
    ------
    str
        The names of available serial ports compatible with the Bpod device.

    Notes
    -----
    The method employs a brief timeout when opening each port to minimize the impact on
    system resources.

    SerialException is caught and ignored, allowing the method to continue scanning even
    if certain ports encounter errors during opening.

    Examples
    --------

    .. code-block:: python

        for port in Bpod.find():
            print(f"Bpod on {port}")
        # Bpod on COM3
        # Bpod on COM6
    """
    for port in (p for p in list_ports.comports() if p.vid == 0x16C0):
        try:
            with serial.Serial(port.name, timeout=0.2) as ser:
                if ser.read(1) == bytes([222]):
                    yield port.name
        except serial.SerialException:
            pass
