from socket_baseclass import *


class EchoClient(BaseClientApplication):
    def recv_callback(self, data: bytes, sock: socket.socket):
        print(f"server responded: ({data})")
        return


client = EchoClient((CLIENT_HOST, CLIENT_PORT))
client.run()

while True:
    print("//////////////////////////////////////")
    inp = input("message: ")
    if inp == "q":
        client.close()
        break
    else:
        client.send(inp.encode())
