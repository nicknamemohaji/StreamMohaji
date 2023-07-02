from socket_baseclass import BaseServerApplication
from datetime import datetime
from typing import TypedDict
import socket
import selectors
import os
import uuid


class RTMPHeader:
    """
    handling rtmp chunk header.
    - make an object with kwargs then use compile method to compile header
    - make an object with arg, only accepting [packet: bytes],
        then use parse method to parse received header
    """
    # define constants
    TIMESTAMP_MAX = 0xFFFFFF

    # define object keys
    chunk_stream_id = None
    timestamp_delta = None
    message_length = None
    message_type = None
    message_stream_id = None
    header_index = None

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

        if len(args) == 1:
            self.parse(args[0])

        return

    def parse(self, packet: bytes):
        mheader, msg = self.parse_chunk_header(packet)
        return (mheader, msg,)

    def parse_chunk_header(self, packet):
        _packet = packet[:]

        # Basic Header
        fmt = packet[0] & 0b11000000

        cs_id = packet[0] & 0b00111111
        if cs_id == 0:  # 2 bytes chunk stream id
            cs_id = int(packet[1]) + 64
            packet = packet[2:]
        elif cs_id == 1:  # 3 bytes chunk stream id
            cs_id = int(packet[2]) * 256 + int(packet[1]) * 64 + 64
            packet = packet[3:]
        else:  # 1 byte chunk stream id
            cs_id = int(cs_id)
            packet = packet[1:]
        self.chunk_stream_id = cs_id

        # Message Header

        if fmt == 0:  # type 0: 11 bytes
            mheader = packet[:11]
            msg = packet[11:]
        elif fmt == 1:  # type 1: 7 bytes
            mheader = packet[:7]
            msg = packet[7:]
        elif fmt == 2:  # type 2: 3 bytes
            mheader = packet[:3]
            msg = packet[3:]
        else:  # type 3: no message header
            mheader = []
            msg = packet[:]

        timedelta = int.from_bytes(mheader[0:3], 'big') if fmt < 3 else None
        mlen = int.from_bytes(mheader[4:6], 'big') if fmt < 2 else None
        mtype = mheader[6] if fmt < 2 else None
        mstreamid = int.from_bytes(mheader[7:], 'little') if fmt < 1 else None

        # Extended Timestamp (optional)

        if timedelta is not None and timedelta == self.TIMESTAMP_MAX:
            timedelta = int.from_bytes(msg[0:4], 'big')
            msg = msg[4:]

        # Save..
        self.timestamp_delta = timedelta
        self.message_length = mlen
        self.message_type = mtype,
        self.message_stream_id = mstreamid
        self.header_index = len(_packet) - len(msg)

        return mheader, msg

    def compile(self):
        # TODO
        raise NotImplementedError


class RTMPPayload:
    """
    handling rtmp chunk payload.
    - make an object with kwargs then use compile method to compile payload
    - make an object with args, whose order is [header, Protocol.header, packet: bytes],
        then use parse method to parse received payload
    """

    # define constants
    # 1. protocol control messages
    TYPE_CONTROL_SET_CHUNK = 1
    TYPE_CONTROL_ABORT_MESSAGE = 2
    TYPE_CONTROL_ACK = 3
    TYPE_CONTROL_ACK_SIZE = 5
    TYPE_CONTROL_SET_BANDWIDTH = 6
    RTMP_CONTROL_TYPES = [TYPE_CONTROL_SET_CHUNK, TYPE_CONTROL_ABORT_MESSAGE,
                          TYPE_CONTROL_ACK, TYPE_CONTROL_ACK_SIZE, TYPE_CONTROL_SET_BANDWIDTH]

    # 2. streaming control message
    TYPE_USER_CONTROL_MESSAGE = 4

    # 3. amf0 encoded message
    TYPE_AMF0_COMMAND = 20
    TYPE_AMF0_DATA = 18
    TYPE_AMF0_SO = 19

    # 4. amf3 encoded message
    TYPE_AMF3_COMMAND = 17
    TYPE_AMF3_DATA = 15
    TYPE_AMF3_SO = 16

    # 5. misc types
    TYPE_VIDEO = 9
    TYPE_AUDIO = 8
    TYPE_AGGREGATE = 22

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

        if len(args) == 1:
            self.parse(args[0], args[1])

        return

    def parse(self, header: RTMPHeader, packet: bytes):
        if header.message_type in self.RTMP_CONTROL_TYPES and header.chunk_stream_id == 2:
            # Protocol Control Message
            self.parse_protocol_control_message(header, packet)

        return

    def parse_protocol_control_message(self, header: RTMPHeader, msg: bytes):
        # TODO
        if header.message_type == self.TYPE_CONTROL_SET_CHUNK:
            pass
        elif header.message_type == self.TYPE_CONTROL_ABORT_MESSAGE:
            pass
        elif header.message_type == self.TYPE_CONTROL_ACK:
            pass
        elif header.message_type == self.TYPE_CONTROL_ACK_SIZE:
            pass
        elif header.message_type == self.TYPE_CONTROL_SET_CHUNK:
            pass

        return msg

    def compile(self):
        # TODO
        raise NotImplementedError


class Protocol:
    header = None
    body = None

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

        if len(args) == 1:
            self.parse(args[0])

        return

    def parse(self, msg: bytes):
        self.header = RTMPHeader(msg)
        body_bytes = msg[self.header.header_index:]
        print(msg)
        print(self.header.header_index)
        print(body_bytes)
        self.body = RTMPPayload(body_bytes)

        print()
        print(self.header.__dict__)
        print()
        print(self.body.__dict__)

        return


class RtmpBaseServer(BaseServerApplication):
    class StreamObject:
        sock: socket.socket
        stream_id: str
        stream_path: str
        max_size: int

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def __init__(self, addr: tuple, path: str):
        super().__init__(addr)

        self.streams = dict()
        self.save_path = path

        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
        self.socket.setblocking(True)

    def accept(self, socket_obj: socket.socket, sel: selectors.BaseSelector):
        client, addr = socket_obj.accept()
        self.sel.register(client, selectors.EVENT_READ, self.recv)
        self.clients.append(client)
        print(f"[{datetime.now().isoformat()}] starting handshake with ({addr[0]}:{addr[1]})...")

        # >>> handshake
        """
        softwares like OBS sends c0+c1 together and expects to receive s0+s1 together... TF??
        """
        c1 = None
        FLAG_c0c1 = False

        # 1. receive c0
        self.sel.select(1)
        c0 = client.recv(1537)
        if len(c0) == 1537:
            # c0 + c1 received
            c1 = c0[1:]
            c0 = c0[0]
            FLAG_c0c1 = True
        elif len(c0) != 1:
            print(f"received len ({len(c0)}). expecting c0(1) or c0+c1(1537). abort.")
            self.remove_client(client)

        if c0 != 3:
            print(f"received ({c0}), expecting (3). trying to downgrade...")

        # 2. receive c1
        if c1 is None:
            self.sel.select(1)
            c1 = client.recv(1536)
        if len(c1) != 1536 or c1[4:8] != b'\00' * 4:
            print("not valid c1 packet. abort")
            self.remove_client(client)
            return
        c1_time = c1[:4]
        c1_random = c1[8:]

        if FLAG_c0c1:
            rand = os.urandom(1528)
            client.send(b'\x03' + b'\x00' * 4 + b'\x00' * 4 + rand)
        else:
            # 3. send s0
            client.send(b'\x03')

            # 4. send s1
            rand = os.urandom(1528)
            client.send(b'\x00' * 4 + b'\x00' * 4 + rand)

        # 5. receive c2
        self.sel.select(1)
        c2 = client.recv(1536)
        if len(c2) != 1536:
            print("not a valid c2 packet. abort")
            client.close()
            return
        if c2[8:] != rand or c2[0:4] != b'\00' * 4:
            print("peer sent wrong echo for c2 packet. abort")
            self.remove_client(client)
            return

        # 6. send s2
        client.send(c1_time + b'\x00' * 4 + c1_random)

        # <<<< handshake done
        print(f"[{datetime.now().isoformat()}] handshake with ({addr[0]}:{addr[1]}) finished")

        # save stream socket
        stream_id = uuid.uuid4().__str__()
        stream_path = self.save_path + stream_id + "\\"
        os.makedirs(stream_path)
        stream = self.StreamObject(sock=client,
                                   max_size=1024 * 1024,  # max_size should be set after first type0 packet is sent
                                   stream_id=stream_id, stream_path=stream_path)
        self.streams[client] = stream

        return

    def recv(self, sock: socket.socket, sel: selectors.BaseSelector):
        """
        override BaseServerApplication.recv function to use stream max buffer size
        """
        stream = self.streams[sock]
        data = sock.recv(stream.max_size + 18)  # max header size is 3 + 11 + 4

        # check EOT
        if data:
            print(f"[{datetime.now().isoformat()}] received data from ({sock.getpeername()}): length ({len(data)})")

            # call callback function
            self.recv_callback(data, sock)
        else:  # EOT packet
            print(f"[{datetime.now().isoformat()}] received EOT from ({sock.getpeername()}")
            self.remove_client(sock)

    def recv_callback(self, data: bytes, sock: socket.socket):

        print(len(data))

        stream = self.streams[sock]
        chunk = Protocol(data)

        print(chunk)

        pass
