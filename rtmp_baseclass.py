from datetime import datetime
from rtmp_errors import *
from rtmp_stream import StreamObject
from rtmp_protocol import *
import socket
import selectors
import os
import uuid


class RtmpBaseServer:
    def __init__(self, addr: tuple, path: str):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.socket.setblocking(True)

        self.addr = addr
        self.sel = selectors.DefaultSelector()
        self.clients = []

        self.streams = dict()
        self.save_path = path

    def remove_client(self, sock: socket.socket):
        sock.close()
        self.sel.unregister(sock)
        self.clients.remove(sock)

        return

    def recv(self, sock: socket.socket, sel: selectors.BaseSelector):
        stream = self.streams[sock]

        # check EOT
        data = sock.recv((stream.max_size + 18) * 2)    # prepare for buffer stack..
        if data:
            print(f"[{datetime.now().isoformat()}] received data from ({sock.getpeername()}): length ({len(data)})")
            # call callback function
            self.recv_callback(data, sock)
        else:  # EOT packet
            print(f"[{datetime.now().isoformat()}] received EOT from ({sock.getpeername()}")
            self.remove_client(sock)

    def accept(self, socket_obj: socket.socket, sel: selectors.BaseSelector):
        client, addr = socket_obj.accept()
        client.setblocking(True)
        print(f"[{datetime.now().isoformat()}] starting handshake with ({addr[0]}:{addr[1]})...")

        # >>> handshake
        """
        softwares like OBS sends c0+c1 together and expects to receive s0+s1 together... TF??
        """
        c1 = None
        FLAG_c0c1 = False

        # 1. receive c0
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

        rand = os.urandom(1528)
        # rand = b'\x00' * 1528
        if FLAG_c0c1:
            client.send(b'\x03' + b'\x00' * 4 + b'\x00' * 4 + rand)
        else:
            # 3. send s0
            client.send(b'\x03')

            # 4. send s1
            client.send(b'\x00' * 4 + b'\x00' * 4 + rand)

        # 5. send s2
        client.send(c1_time + b'\x00' * 4 + c1_random)

        # 6. receive c2
        c2 = client.recv(1536)
        if len(c2) != 1536:
            print("not a valid c2 packet. abort")
            client.close()
            return
        if c2[8:] != rand or c2[0:4] != b'\00' * 4:
            print("peer sent wrong echo for c2 packet. abort")
            self.remove_client(client)
            return

        # <<<< handshake done
        print(f"[{datetime.now().isoformat()}] handshake with ({addr[0]}:{addr[1]}) finished")
        client.setblocking(False)

        # save stream socket
        stream_id = uuid.uuid4().__str__()
        stream_path = self.save_path + stream_id + "\\"
        os.makedirs(stream_path)
        stream = StreamObject(sock=client,
                              max_size=1024 * 1024,  # max_size should be set after first type0 packet is sent
                              stream_id=stream_id, stream_path=stream_path)
        self.streams[client] = stream
        self.clients.append(client)
        self.sel.register(client, selectors.EVENT_READ, self.recv)

        return

    def recv_callback(self, data: bytes, sock: socket.socket):
        stream = self.streams[sock]

        try:
            chunk = RTMP(data, stream)
            stream.FLAG_CHUNK_PENDING = False
            stream.chunk_pending = bytes()
        except RTMP_ChunkNotFullyReceived:
            print(f"status: [pending] {stream.FLAG_CHUNK_PENDING}, [buffer] {stream.chunk_pending}")
            stream.FLAG_CHUNK_PENDING = True
            stream.chunk_pending += data

    def run(self):
        self.socket.bind(self.addr)
        self.socket.listen()
        print(f"[*] server listening on {self.addr[0]}:{self.addr[1]}")

        self.sel.register(self.socket, selectors.EVENT_READ, self.accept)

        while True:
            events = self.sel.select(-1)
            for key, _ in events:
                callback = key.data
                callback(key.fileobj, self.sel)

    def close(self):
        for c in self.clients:
            self.remove_client(c)

        self.sel.unregister(self.socket)
        self.sel.close()

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            self.socket.close()

        return
