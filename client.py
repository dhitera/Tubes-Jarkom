import socket
import time
import argparse
import threading

BUFFER_SIZE = 4096
DEFAULT_HTTP_PORT = 8080
DEFAULT_UDP_PORT = 9090


def http_client(ip, port, path, client_id):
    start = time.time()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))

            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {ip}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )

            s.sendall(request.encode())
            response = b""

            while True:
                data = s.recv(BUFFER_SIZE)
                if not data:
                    break
                response += data

        sep = response.find(b"\r\n\r\n")
        body = response[sep + 4:] if sep != -1 else response

        filename = f"client_{client_id}_output.html"
        with open(filename, "wb") as f:
            f.write(body)

        print(f"[Client {client_id}] HTML disimpan ke {filename}")
        print(f"[Client {client_id}] Waktu {time.time() - start:.4f}s")

    except Exception as e:
        print(f"[Client {client_id}] Error: {e}")


def udp_client(ip, port, client_id, count, size, interval):
    sent = received = 0
    rtts = []

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(2)

        for i in range(count):
            payload = f"{client_id}-{i}".encode().ljust(size, b"x")
            sent_time = time.time()
            s.sendto(payload, (ip, port))
            sent += 1

            try:
                s.recvfrom(BUFFER_SIZE)
                rtts.append(time.time() - sent_time)
                received += 1
            except socket.timeout:
                pass

            time.sleep(interval)

    loss = (sent - received) / sent * 100 if sent else 0
    avg_rtt = sum(rtts) / len(rtts) if rtts else 0

    print(f"[Client {client_id}] UDP Result")
    print(f"  Sent      : {sent}")
    print(f"  Received  : {received}")
    print(f"  Loss      : {loss:.2f}%")
    print(f"  Avg RTT   : {avg_rtt * 1000:.2f} ms")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    tcp = sub.add_parser("tcp")
    tcp.add_argument("--ip", required=True)
    tcp.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    tcp.add_argument("--path", default="/")
    tcp.add_argument("--clients", type=int, default=1)

    udp = sub.add_parser("udp")
    udp.add_argument("--ip", required=True)
    udp.add_argument("--port", type=int, default=DEFAULT_UDP_PORT)
    udp.add_argument("--clients", type=int, default=1)
    udp.add_argument("--count", type=int, default=20)
    udp.add_argument("--size", type=int, default=100)
    udp.add_argument("--interval", type=float, default=0.1)

    args = parser.parse_args()

    threads = []

    if args.mode == "tcp":
        for i in range(1, args.clients + 1):
            t = threading.Thread(
                target=http_client,
                args=(args.ip, args.port, args.path, i)
            )
            t.start()
            threads.append(t)

    else:
        for i in range(1, args.clients + 1):
            t = threading.Thread(
                target=udp_client,
                args=(args.ip, args.port, i,
                      args.count, args.size, args.interval)
            )
            t.start()
            threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
