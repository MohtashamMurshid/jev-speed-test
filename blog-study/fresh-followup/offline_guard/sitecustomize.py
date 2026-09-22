"""Network guard used only by reproduce.py subprocesses."""
import socket


def blocked(*args, **kwargs):
    raise RuntimeError('Network disabled during offline reproduction')


socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
