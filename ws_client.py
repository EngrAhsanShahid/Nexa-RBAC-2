"""Simple websocket client for the camera_rbac service.

Connects to the websocket endpoint and prints every message received until
the connection closes.
"""

from __future__ import annotations

import argparse
import asyncio

import websockets


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8000


def build_websocket_url(host: str, port: int, tenant_id: str, token: str) -> str:
    return f"ws://{host}:{port}/ws/{tenant_id}?token={token}"


async def listen(websocket_url: str) -> None:
    async with websockets.connect(websocket_url) as websocket:
        print(f"Connected to {websocket_url}")
        try:
            async for message in websocket:
                print(message)
        except websockets.ConnectionClosed as exc:
            print(f"Connection closed: code={exc.code} reason={exc.reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Connect to the camera_rbac websocket and print incoming messages."
    )
    parser.add_argument("--tenant_id", help="Tenant id used in the websocket path",default="tenant_1")
    parser.add_argument("--token", help="JWT token passed as the token query parameter", default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWYwOTllMjU1YTcyMmEyNjAyMTEwODAiLCJyb2xlIjoiQWRtaW4iLCJleHAiOjE3Nzc5NzM0MDN9.ANj53g95vmdWtSQqdaq-0r6I030CPDddhtRgMEeoHtQ")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Websocket host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Websocket port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    websocket_url = build_websocket_url(args.host, args.port, args.tenant_id, args.token)

    try:
        asyncio.run(listen(websocket_url))
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()