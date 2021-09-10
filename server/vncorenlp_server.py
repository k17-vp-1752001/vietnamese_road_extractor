import os
import socket
from contextlib import closing
import time
import subprocess

import psutil
from psutil import net_connections


DEFAULT_FAR_FILE = r'VnCoreNLP/VnCoreNLP-1.1.1.jar'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 9000


class VNCoreNLPServer:

    def __init__(self, jar_file=DEFAULT_FAR_FILE, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.jar_file = jar_file
        self.host = host
        self.port = port
        self.cmd = 'vncorenlp ' + self.jar_file + ' -p ' + str(self.port) + ' -a "wseg,pos,ner,parse"'
        self.process = None

    def start(self):
        if not self.is_running():
            print("Starting server...")
            self.process = subprocess.Popen(self.cmd.split(' '), stdout=subprocess.PIPE)
            wait_for_port(host=self.host, port=self.port, operation='open')
            print('Server started')
            return 1
        else:
            print("Server is already running")

    def is_running(self):
        if self.process:
            return True
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex((self.host, self.port)) == 0:
                print("Port is open")
                return True
            else:
                print("Port is not open")
                return False

    def close(self):
        if self.is_running():
            if self.process is not None:
                print('Shutting down server...')
                self.process.terminate()
                print('Server shutdown')
                return 1
            # Search process PID and manually terminate instead
            pid = None
            for conn in net_connections(kind='inet'):
                if conn.laddr == (self.host, self.port):
                    pid = conn.pid
                    break

            if pid is not None:
                print('Shutting down server...')
                psutil.Process(pid).terminate()
                wait_for_port(host=self.host, port=self.port, operation='close')
                print('Server shutdown')
                return 1
            else:
                print('Server is running but cannot find server process')
                return 0
        else:
            print('Server is not running')
            return 0


def wait_for_port(port, host='localhost', operation='open'):
    """Wait until a port starts accepting TCP connections.
    Args:
        port (int): Port number.
        host (str): Host address on which the port should exist.
        operation (str): Open or Close depends on action op waiting
    Raises:
        TimeoutError: The port isn't accepting connection after time specified in `timeout`.
    """
    waiting_open = False
    if operation.lower() == 'open':
        waiting_open = True

    while True:
        try:
            with socket.create_connection((host, port)):
                if waiting_open:
                    break
        except Exception as e:
            if not waiting_open:
                break
            else:
                pass
