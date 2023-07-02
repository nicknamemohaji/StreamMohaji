from socket_baseclass import *


class EchoServer(BaseServerApplication):
    def recv_callback(self, msg: bytes, sock: socket.socket):
        peer = "{0[0]}:{0[1]}".format(sock.getpeername())
        print(f"[{datetime.now().isoformat()}] echoing: ({msg}) from ({peer})")
        self.broadcast(f"echo from ({peer}): ".encode() + msg)


server = EchoServer((SERVER_HOST, SERVER_PORT))
server.run()
