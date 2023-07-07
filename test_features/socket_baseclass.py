import selectors
import socket
import threading
from datetime import datetime

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 12345
CLIENT_HOST = '127.0.0.1'
CLIENT_PORT = 12345
MAX_BUFFER_SIZE = 4 * 1024


class BaseServerApplication:
    def __init__(self, addr: tuple, option: dict = None):
        """
        Base server application wrapper for socket transmission
        :param addr: tuple: (ip: string, port: int)-
        """
        # bind socket and set to non-blocking io
        if option is not None:
            self.socket = socket.socket(**option)
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.addr = addr
        self.sel = selectors.DefaultSelector()
        self.clients = []

        return

    def accept(self, socket_obj: socket.socket, sel: selectors.BaseSelector):
        """
        this is callback function handling `socket.accept()`
        """

        client, addr = socket_obj.accept()
        print(f"[{datetime.now().isoformat()}] connection from ({addr[0]}:{addr[1]}) accepted")

        self.sel.register(client, selectors.EVENT_READ, self.recv)
        self.clients.append(client)

        return

    def recv(self, sock: socket.socket, sel: selectors.BaseSelector):
        # check EOT
        data = sock.recv(MAX_BUFFER_SIZE)
        if data:
            print(f"[{datetime.now().isoformat()}] received data from ({sock.getpeername()}): length ({len(data)})")
            # call callback function
            self.recv_callback(data, sock)
        else:  # EOT packet
            print(f"[{datetime.now().isoformat()}] received EOT from ({sock.getpeername()}")
            self.remove_client(sock)

    def remove_client(self, sock: socket.socket):
        sock.close()
        self.sel.unregister(sock)
        self.clients.remove(sock)

        return

    def recv_callback(self, data: bytes, sock: socket.socket):
        """
        should be rewritten in server implementation
        """
        raise NotImplementedError

    def broadcast(self, msg):
        for c in self.clients:
            c.send(msg)
        print(f"[{datetime.now().isoformat()}] broadcast success: ({msg}) to ({len(self.clients)}) clients")

        return

    def run(self):
        self.socket.bind(self.addr)
        self.socket.listen()
        self.socket.setblocking(False)
        print(f"[*] server listening on {SERVER_HOST}:{SERVER_PORT}")

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


class BaseClientApplication:
    def __init__(self, addr: tuple):
        self.socket = socket.create_connection(addr)

        self.threads = []
        self.thread_event = threading.Event()
        self.thread_event.clear()

        self.sel = selectors.DefaultSelector()
        self.sel.register(self.socket, selectors.EVENT_READ, self.__recv)

        return

    def __recv(self, sock: socket.socket, sel: selectors.BaseSelector):
        # check EOT
        data = sock.recv(MAX_BUFFER_SIZE)
        if data:
            print(f"[{datetime.now().isoformat()}] received data: length ({len(data)})")
            # call callback function
            self.recv_callback(data, sock)
        else:  # EOT packet
            print(f"[{datetime.now().isoformat()}] received EOT")
            self.close()

    def recv_callback(self, data: bytes, sock: socket.socket):
        """
        should be rewritten in server implementation
        """
        raise NotImplementedError

    def add_thread(self):
        def watcher(blocker: threading.Event):
            while blocker.is_set():
                event = self.sel.select(-1)
                for key, mask in event:
                    callback = key.data
                    callback(key.fileobj, self.sel)
            return

        t = threading.Thread(target=watcher, args=(self.thread_event,))
        self.threads.append(t)

    def send(self, msg: bytes):
        self.socket.send(msg)
        return

    def run(self):
        self.add_thread()
        self.thread_event.set()

        for t in self.threads:
            t.start()

        return

    def close(self):
        self.thread_event.clear()
        for t in self.threads:
            t.join()

        self.sel.unregister(self.socket)
        self.sel.close()

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            self.socket.close()

        return
