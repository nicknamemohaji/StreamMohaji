from rtmp_errors import *
from rtmp_stream import StreamObject
from amf0_protocol import AMF0
from rtmp_constants import *


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
    header_index = 0

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
        self.timestamp_delta = timedelta
        self.message_length = mlen
        self.message_type = mtype
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
        if header.message_type in RTMP_CONTROL_TYPES and header.chunk_stream_id == 2:
            # Protocol Control Message
            self.parse_protocol_control_message(header, packet, stream)
        elif header.message_type == TYPE_USER_CONTROL_MESSAGE:
            # TODO
            pass
        elif header.message_type in AMFO_TYPES:
            # AMF0 encoded message
            self.parse_amf0(header, packet, stream)

        return

    def parse_amf0(self, header: RTMPHeader, msg: bytes, stream: StreamObject):
        # TODO
        _ = AMF0()
        amf0_obj = _.parse(msg)
        if header.message_type == TYPE_AMF0_COMMAND:
            pass

    def parse_protocol_control_message(self, header: RTMPHeader, msg: bytes,
                                       stream: StreamObject):
        if header.message_type == TYPE_CONTROL_SET_CHUNK:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            size = int.from_bytes(msg, 'big') & 0x7fff
            stream.max_size = size
            print(f"set max buffer size to {stream.max_size}")
            return True
        elif header.message_type == TYPE_CONTROL_ABORT_MESSAGE:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            chunk_id = int.from_bytes(msg, 'big')
            # TODO
            pass
        elif header.message_type == TYPE_CONTROL_ACK:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            seq_no = int.from_bytes(msg, 'big')
            # TODO
        elif header.message_type == TYPE_CONTROL_ACK_SIZE:
            if len(msg) != 4:
                raise RTMP_MultiplePacketsInBuffer
            window_size = int.from_bytes(msg, 'big')
            # TODO
            pass
        elif header.message_type == TYPE_CONTROL_SET_BANDWIDTH:
            if len(msg) != 5:
                raise RTMP_MultiplePacketsInBuffer
            window_size = int.from_bytes(msg, 'big')
            limit_type = msg[4]
            # TODO
            if limit_type == 0:  # type 0: HARD limit
                pass
            elif limit_type == 1:  # type 1: SOFT limit
                pass
            else:  # type 2: DYNAMIC limit
                pass

            pass

        return False

    def compile(self):
        # TODO
        raise NotImplementedError


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
        {
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
        pass
