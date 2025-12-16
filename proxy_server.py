import socket
import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor

PROXY_HTTP_PORT = 8080
PROXY_UDP_PORT = 9090

BACKEND_HTTP_HOST = "10.0.2.15"
BACKEND_HTTP_PORT = 8000
BACKEND_UDP_HOST = "10.0.2.15"
BACKEND_UDP_PORT = 9000

BUFFER_SIZE = 4096
TIMEOUT = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

cache = {}
cache_lock = threading.Lock()


def send_error(conn, status_line, message):
    body = f"<h1>{message}</h1>".encode("utf-8")
    response = (
        f"{status_line}"
        f"Content-Length: {len(body)}\r\n"
        f"Content-Type: text/html\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8") + body

    try:
        conn.sendall(response)
    except Exception:
        pass


def handle_tcp_client(conn, addr):
    start = time.time()
    conn.settimeout(TIMEOUT)

    try:
        request = conn.recv(BUFFER_SIZE)
        if not request:
            return

        first_line = request.decode("utf-8", errors="ignore").splitlines()[0]

        with cache_lock:
            cached_response = cache.get(first_line)

        if cached_response:
            conn.sendall(cached_response)
            logging.info(
                f"TCP PROXY | {addr[0]} cache HIT "
                f"size={len(cached_response)}B "
                f"time={time.time() - start:.4f}s"
            )
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as backend:
            backend.settimeout(TIMEOUT)
            backend.connect((BACKEND_HTTP_HOST, BACKEND_HTTP_PORT))
            backend.sendall(request)

            response_parts = []
            while True:
                data = backend.recv(BUFFER_SIZE)
                if not data:
                    break
                response_parts.append(data)

        if not response_parts:
            send_error(conn, "HTTP/1.1 502 Bad Gateway\r\n", "502 Bad Gateway")
            return

        response = b"".join(response_parts)

        with cache_lock:
            cache[first_line] = response

        conn.sendall(response)

        logging.info(
            f"TCP PROXY | {addr[0]} -> {BACKEND_HTTP_HOST} "
            f"cache MISS size={len(response)}B "
            f"time={time.time() - start:.4f}s"
        )

    except socket.timeout:
        send_error(conn, "HTTP/1.1 504 Gateway Timeout\r\n", "504 Gateway Timeout")
    except Exception as e:
        logging.error(f"TCP PROXY error {addr}: {e}")
        send_error(conn, "HTTP/1.1 502 Bad Gateway\r\n", "502 Bad Gateway")
    finally:
        conn.close()


def tcp_proxy_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", PROXY_HTTP_PORT))
        s.listen()

        logging.info(f"TCP Proxy listening on port {PROXY_HTTP_PORT}")

        with ThreadPoolExecutor(max_workers=20) as executor:
            while True:
                conn, addr = s.accept()
                executor.submit(handle_tcp_client, conn, addr)


def udp_proxy_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", PROXY_UDP_PORT))
        logging.info(f"UDP Proxy listening on port {PROXY_UDP_PORT}")

        while True:
            data, client_addr = s.recvfrom(BUFFER_SIZE)
            start = time.time()

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as backend:
                backend.settimeout(TIMEOUT)
                backend.sendto(data, (BACKEND_UDP_HOST, BACKEND_UDP_PORT))

                try:
                    resp, _ = backend.recvfrom(BUFFER_SIZE)
                    s.sendto(resp, client_addr)
                    logging.info(
                        f"UDP PROXY | {client_addr[0]} "
                        f"size={len(data)}B "
                        f"time={time.time() - start:.4f}s"
                    )
                except socket.timeout:
                    logging.warning(f"UDP PROXY timeout {client_addr[0]}")


def main():
    udp_thread = threading.Thread(target=udp_proxy_server, daemon=True)
    udp_thread.start()
    tcp_proxy_server()


if __name__ == "__main__":
    main()
