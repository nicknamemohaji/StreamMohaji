from rtmp_baseclass import RtmpBaseServer
import os

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 12345

server = RtmpBaseServer((SERVER_HOST, SERVER_PORT,), os.getcwd() + "\\temp\\")
server.run()
