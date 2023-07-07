from rtmp_errors import *
from rtmp_stream import StreamObject
from amf0_protocol import AMF0
from rtmp_constants import *
import time
import struct


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
    chunk_type = None
    message_stream_id = None
    fmt = None
    header_index = 0

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

        if len(args) == 1:
            self.parse(args[0])

        return

    def parse(self, packet: bytes):
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
        elif fmt == 3:  # type 3: no message header
            mheader = []
            msg = packet[:]
        else:
            raise RTMP_NotHeader

        timedelta = int.from_bytes(mheader[0:3], 'big') if fmt < 3 else None
        mlen = int.from_bytes(mheader[3:6], 'big') if fmt < 2 else None
        mtype = mheader[6] if fmt < 2 else None
        mstreamid = int.from_bytes(mheader[7:], 'little') if fmt < 1 else None

        # Extended Timestamp (optional)
        if timedelta is not None and timedelta == self.TIMESTAMP_MAX:
            timedelta = int.from_bytes(msg[0:4], 'big')
            msg = msg[4:]

        # Save..
        self.fmt = fmt
        self.timestamp_delta = timedelta
        self.message_length = mlen
        self.chunk_type = mtype
        self.message_stream_id = mstreamid
        self.header_index = len(_packet) - len(msg)

        return mheader, msg

    def compile(self):
        if any([_ is None for _ in self.__dict__]):
            raise TypeError("not enough argument for RTMPHeader.compile")

        # Basic Header
        if self.fmt not in [0, 1, 2, 3]:
            raise TypeError("message type should be one of (0, 1, 2, 3)")
        if self.chunk_stream_id < 2 or self.chunk_stream_id > 65597:
            raise TypeError("chunk stream id should be in range [2, 65597]")
        elif self.chunk_stream_id < 63:
            res = struct.pack('>B', (self.fmt << 6) + self.chunk_stream_id)
        elif self.chunk_stream_id < 319:
            res = struct.pack('>B', (self.fmt << 6)) + \
                  struct.pack('>B', self.chunk_stream_id - 64)
        else:
            res = struct.pack('>B', (self.fmt << 6)) + \
                  struct.pack('>B', self.chunk_stream_id - 64) + \
                  struct.pack('>B', self.chunk_stream_id // 256)

        # Message Header
        if self.fmt < 3:  # timestamp
            if self.timestamp_delta >= self.TIMESTAMP_MAX:
                res += struct.pack('>I', self.TIMESTAMP_MAX)[1:]
            else:
                res += struct.pack('>I', self.timestamp_delta)[1:]
        if self.fmt < 2:
            res += struct.pack('>I', self.message_length)[1:]  # message length
            res += struct.pack('>B', self.chunk_type)  # message type
        if self.fmt == 0:  # message stream id
            res += struct.pack('>I', self.message_stream_id)[1:]

        # extended timestamp
        if self.timestamp_delta >= self.TIMESTAMP_MAX:
            res += struct.pack('>I', self.timestamp_delta)

        return res


class RTMPPayload:
    """
    handling rtmp chunk payload.
    - make an object with kwargs then use compile method to compile payload
    - make an object with args, whose order is [header, Protocol.header, packet: bytes],
        then use parse method to parse received payload
    """

    def __init__(self, *args, **kwargs):
        """

        :param args: [header: RTMPHeader, payload: bytes, stream: RTMPStreamObject]
        :param kwargs:
        """
        self.__dict__.update(kwargs)

        if len(args) == 3:
            self.parse(args[0], args[1], args[2])

        return

    def parse(self, header: RTMPHeader, packet: bytes, stream: StreamObject):
        if header.chunk_type in RTMP_CONTROL_TYPES and header.chunk_stream_id == RTMP_CONTROL_CID:
            # Protocol Control Message
            self.parse_protocol_control_message(header, packet, stream)
        elif header.chunk_type == TYPE_USER_CONTROL_MESSAGE:
            # TODO implement user control message
            pass
        elif header.chunk_type in AMFO_TYPES:
            # TODO implement AMF0 encoded message
            self.parse_amf0(header, packet, stream)
        elif header.chunk_type in AMF3_TYPES:
            # TODO implement AMF3 encoded message
            pass

        return

    def parse_amf0(self, header: RTMPHeader, msg: bytes, stream: StreamObject):
        # TODO execute message provided
        amf = AMF0(msg)
        amf0_obj = amf.obj
        if header.chunk_type == TYPE_AMF0_COMMAND:
            pass

    def parse_protocol_control_message(self, header: RTMPHeader, msg: bytes,
                                       stream: StreamObject):
        if header.chunk_type == TYPE_CONTROL_SET_CHUNK:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            size = int.from_bytes(msg, 'big') & 0x7fff
            stream.max_size = size
            print(f"set max buffer size to {stream.max_size}")
            return True
        elif header.chunk_type == TYPE_CONTROL_ABORT_MESSAGE:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            chunk_id = int.from_bytes(msg, 'big')
            # TODO implement control message
            pass
        elif header.chunk_type == TYPE_CONTROL_ACK:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            seq_no = int.from_bytes(msg, 'big')
            # TODO implement control message
        elif header.chunk_type == TYPE_CONTROL_ACK_SIZE:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            window_size = int.from_bytes(msg, 'big')
            # TODO implement control message
            pass
        elif header.chunk_type == TYPE_CONTROL_SET_BANDWIDTH:
            if len(msg) != 5:
                raise RTMP_MultiplePacketsInBuffer
            window_size = int.from_bytes(msg, 'big')
            limit_type = msg[4]
            # TODO implement control message
            if limit_type == 0:  # type 0: HARD limit
                pass
            elif limit_type == 1:  # type 1: SOFT limit
                pass
            else:  # type 2: DYNAMIC limit
                pass

            pass

        return False


def _merge(li: list):
    while True:
        if any([isinstance(_, list) for _ in li]):
            tmp = li
            li = li[:-1]
            li.append(tmp[-1][0])
            li.append(tmp[-1][1])
        else:
            break
    return li


class RTMP:
    header = None
    body = None

    def __init__(self, *args, **kwargs):
        """
        :param args:  accepts two argument: [packet: bytes, stream: RtmpBaseServer.StreamObject]
        :param kwargs:  used to set variable when compiling:
        {mtype: int, cid: int, mid: int, timedelta: int, fmt: int, chunk: dict}

        - chunk: dict containing payload values
            - data: bytes
            used when raw values are submitted. this value will be directly sent.  e.g. TYPE_CONTROL_SET_CHUNK
            - message: tuple = *(str | float(fp64) | dict)
            used when sending amf message. object can be a nested dictionary.
            - amf3: bool
            used when sending amf message. true for amf3, false for amf0 encoding
        """
        self.__dict__.update(kwargs)

        if len(args) == 2:
            self.parse(args[0], args[1])

        return

    def parse(self, msg: bytes, stream: StreamObject):
        try:
            self.header = RTMPHeader(msg)
        except RTMP_NotHeader:
            raise RTMP_ChunkNotFullyReceived
        finally:
            body_bytes = msg[self.header.header_index:]

        try:
            self.body = RTMPPayload(self.header, body_bytes, stream)
            ret = [self]
        except RTMP_ChunkNotFullyReceived:
            raise RTMP_ChunkNotFullyReceived
        except RTMP_MultiplePacketsInBuffer:
            idx = len(body_bytes)
            while True:
                try:
                    self.body = RTMPPayload(self.header, body_bytes[:idx], stream)
                    break
                except RTMP_MultiplePacketsInBuffer:
                    idx -= 1
                    continue
            secondary = RTMP(body_bytes[idx:], stream)
            ret = [self, secondary]

        finally:
            ret = _merge(ret)

        return ret

    def compile(self):
        # TODO compile
        if len(self.__dict__) != 6:
            raise TypeError('not enough argument for RTMP.compile')

        if 'data' in self.chunk:  # protocol/user control message TODO support other message type for client support
            payload = self.chunk['data']
        elif 'message' in self.chunk and 'amf3' in self.chunk:  # amf encoded rtmp message
            if self.chunk['amf3']:
                # TODO amf3 compile
                pass
            else:
                amf = AMF0(obj=self.chunk['message'])
            payload = amf.compile()
        else:
            raise TypeError("chunk has no data")

        header = RTMPHeader(chunk_stream_id=self.cid,
                            timestamp_delta=self.timedelta,
                            chunk_type=self.mtype,
                            message_stream_id=self.mid,
                            message_length=len(payload),
                            fmt=self.fmt)
        res = header.compile() + payload

        return res

    def make_protocol_control(self, type: int, data: bytes, timedelta: int):
        args = {
            'mtype': type,
            'cid': RTMP_CONTROL_CID,
            'mid': RTMP_CONTROL_MID,
            'timedelta': timedelta,
            'chunk': {
                'data': data
            },
            'fmt': 0
        }
        self.__dict__.update(args)
        return self.compile()

    def make_control_set_chunk(self, stream: StreamObject, size: int):
        return self.make_protocol_control(
            type=TYPE_CONTROL_SET_CHUNK,
            data=struct.pack('>I', size),
            timedelta=int(time.time() - stream.start_time)
        )

    def make_window_ack(self, stream: StreamObject, size: int):
        return self.make_protocol_control(
            type=TYPE_CONTROL_ACK_SIZE,
            data=struct.pack('>I', size),
            timedelta=int(time.time() - stream.start_time)
        )
