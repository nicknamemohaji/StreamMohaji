import socket


class StreamObject:
    sock: socket.socket
    stream_id: str
    stream_path: str
    max_size: int
    chunk_pending: bytes
    FLAG_CHUNK_PENDING: bool
    last_message_type: int
    ack_window_size: int
    sequence_size: int
    start_time: int

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.FLAG_CHUNK_PENDING = False
        self.chunk_pending = bytes()
        self.last_message_type = -1
