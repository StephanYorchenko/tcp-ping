import random
import socket
import threading
import time

from domain import Message
from .sock_factory import SocketFactory
from .tcp_creator import TCPFactory


class TCPWorker(threading.Thread):
    def __init__(
        self,
        sock_factory: "SocketFactory",
        pack_factory: "TCPFactory",
        resulter,
        timeout,
        k,
        host,
        port,
        seq=0,
        queue=None,
    ):
        super().__init__()
        self.pack_factory = pack_factory
        self.sockets = sock_factory
        self.resulter = resulter
        self.params = [timeout, k, self.get_host(host), queue.get(), port, 0]
        if self.params[2].startswith("127"):
            self.params[1] = "127.0.0.1"
        self.seq = seq
        self.queue = queue

    def _work(self):
        with self.sockets.make(self.params[0]) as sock:
            source = random.randint(10000, 50000)
            packet = self.pack_factory.generate(*self.params[1:], source)
            (timeout, k, host, l, port, _) = self.params
            sock.sendto(packet, (host, 0))
            st = time.time()
            while True:
                try:
                    a = sock.recv(58)
                    if time.time() - st > self.params[0]:
                        raise socket.timeout
                except socket.timeout:
                    if self.params[2].startswith("127"):
                        print(
                                f"seq {self.seq}: tcp response from "
                                f"{host}:{port} [closed] 0s"
                        )
                        response = Message("Ok", 0, _time=0)
                        self.resulter.add_result(response)
                    else:
                        print(f"seq {self.seq}: no response [timeout]")
                        response = Message("timeout", 1)
                    self.resulter.add_result(response)
                    break
                tcp_resp = a[-24:]
                pport = int.from_bytes(tcp_resp[:2], "big")
                psource = int.from_bytes(tcp_resp[2:4], "big")
                if pport != port or psource != source:
                    continue
                e = round((time.time() - st), 3)
                if tcp_resp[12:14] == b"`\x12":
                    print(
                        f"seq {self.seq}: tcp response from "
                        f"{host}:{port} [open] {e}s"
                    )
                elif tcp_resp[12:14] == b"`\x14":
                    print(
                        f"seq {self.seq}: tcp response from "
                        f"{host}:{port} [closed] {e}s"
                    )
                response = Message("Ok", 0, _time=e)
                self.resulter.add_result(response)
                break
            self.queue.task_done()

    @staticmethod
    def get_host(hostname: str) -> str:
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            return ""

    def run(self):
        self._work()
