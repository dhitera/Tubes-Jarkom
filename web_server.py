import socket
import threading
import logging
import os
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

HTTP_PORT = 8000
UDP_PORT = 9000
BUFFER_SIZE = 4096
ROOT_DIR = "www"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def handle_http_client(conn, addr):
    start = time.time()
    conn.settimeout(5)

    try:
        request = conn.recv(BUFFER_SIZE)
        if not request:
            return

        text = request.decode("utf-8", errors="ignore")
        request_line = text.splitlines()[0]
        parts = request_line.split()

        if len(parts) < 2:
            return

        method, path = parts[0], parts[1]
        if path == "/":
            path = "/index.html"

        file_path = os.path.join(ROOT_DIR, path.lstrip("/"))

        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                body = f.read()
            status_line = "HTTP/1.1 200 OK\r\n"
        else:
            body = b"<h1>404 Not Found</h1>"
            status_line = "HTTP/1.1 404 Not Found\r\n"

        response = (
            f"{status_line}"
            f"Content-Length: {len(body)}\r\n"
            f"Content-Type: text/html\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8") + body

        conn.sendall(response)

        duration = time.time() - start
        logging.info(
            f"HTTP | client={addr[0]} file={path} "
            f"size={len(body)}B time={duration:.4f}s"
        )

    except socket.timeout:
        logging.warning(f"HTTP timeout from {addr}")
    except Exception as e:
        logging.error(f"HTTP error from {addr}: {e}")
    finally:
        conn.close()


def http_server(threaded=True, max_workers=10):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", HTTP_PORT))
        s.listen()

        logging.info(
            f"HTTP server listening on port {HTTP_PORT}, threaded={threaded}"
        )

        if threaded:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while True:
                    conn, addr = s.accept()
                    executor.submit(handle_http_client, conn, addr)
        else:
            while True:
                conn, addr = s.accept()
                handle_http_client(conn, addr)


def udp_echo_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", UDP_PORT))
        logging.info(f"UDP echo server listening on port {UDP_PORT}")

        while True:
            data, addr = s.recvfrom(BUFFER_SIZE)
            logging.info(
                f"UDP | from={addr[0]} size={len(data)}B "
                f"time={datetime.now().isoformat()}"
            )
            s.sendto(data, addr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["single", "threaded"], default="threaded")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    threaded = args.mode == "threaded"

    udp_thread = threading.Thread(target=udp_echo_server, daemon=True)
    udp_thread.start()

    http_server(threaded=threaded, max_workers=args.workers)


if __name__ == "__main__":
    main()
