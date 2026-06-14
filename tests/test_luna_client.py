import socket
import threading

from luna_downloader.luna_client import (
    AUTH_PAYLOADS,
    LunaAuthSession,
    parse_luna_index,
    parse_size,
)


def test_parse_size_supports_nginx_units():
    assert parse_size("42") == 42
    assert parse_size("44K") == 44 * 1024
    assert parse_size("2M") == 2 * 1024 * 1024
    assert parse_size("1G") == 1024 * 1024 * 1024


def test_parse_luna_index_extracts_media_files():
    html = """
    <html><body><pre>
    <a href="../">../</a>
    <a href="LRV_20260614_121357_007.lrv">LRV_20260614_121357_007.lrv</a> 14-Jun-2026 12:13 2M
    <a href="VID_20260614_121357_007.mp4">VID_20260614_121357_007.mp4</a> 14-Jun-2026 12:13 11M
    </pre></body></html>
    """

    files = parse_luna_index(
        html,
        "http://192.168.42.1/storage_internal/DCIM/Camera01/",
    )

    assert [item.name for item in files] == [
        "LRV_20260614_121357_007.lrv",
        "VID_20260614_121357_007.mp4",
    ]
    assert files[0].kind == "LRV"
    assert files[1].kind == "MP4"
    assert files[1].size_text == "11M"
    assert files[1].bytes == 11 * 1024 * 1024
    assert files[1].url == (
        "http://192.168.42.1/storage_internal/DCIM/Camera01/"
        "VID_20260614_121357_007.mp4"
    )


def test_luna_auth_session_sends_expected_ucd2_messages():
    received = []
    ready = threading.Event()

    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            received.append(sock.getsockname()[1])
            ready.set()
            conn, _addr = sock.accept()
            with conn:
                for payload in AUTH_PAYLOADS:
                    data = conn.recv(len(payload))
                    received.append(data)
                    conn.sendall(b"UCD2-ACK")

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(2)
    port = received[0]

    with LunaAuthSession("127.0.0.1", port=port, timeout=2) as session:
        assert session.is_open

    assert received[1:] == AUTH_PAYLOADS
