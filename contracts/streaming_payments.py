# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from dataclasses import dataclass, field
from genlayer import *
from typing import Optional


@allow_storage
@dataclass
class StreamState:
    streamer: str = ""
    receiver: str = ""
    rate: u256 = u256(0)
    start_time: u256 = u256(0)
    end_time: u256 = u256(0)
    withdrawn: u256 = u256(0)
    status: str = "active"


class StreamManager(gl.Contract):
    streams: TreeMap[str, StreamState]

    def __init__(self):
        self.streams = TreeMap[str, StreamState]()

    @gl.public.write
    def create_stream(self, receiver: str, amount: u256, duration_seconds: u256) -> str:
        """Create a new stream. Returns stream ID."""
        if amount <= u256(0) or duration_seconds <= u256(0):
            raise Exception("Invalid amount or duration")

        now_ts = u256(gl.now().timestamp)
        rate = amount // duration_seconds
        stream_id = f"{self.address}-{receiver}-{now_ts}"

        stream = StreamState(
            streamer=self.address,
            receiver=receiver,
            rate=rate,
            start_time=now_ts,
            end_time=now_ts + duration_seconds,
        )
        self.streams[stream_id] = stream
        return stream_id

    @gl.public.write
    def stop_stream(self, stream_id: str):
        """Stop an active stream."""
        stream = self.streams.get(stream_id)
        if not stream:
            raise Exception("Stream not found")
        if stream.status != "active":
            raise Exception("Stream already stopped")
        stream.status = "stopped"
        stream.end_time = u256(gl.now().timestamp)

    @gl.public.write
    def withdraw(self, stream_id: str) -> u256:
        """Receiver withdraws accumulated tokens."""
        stream = self.streams.get(stream_id)
        if not stream:
            raise Exception("Stream not found")
        if stream.receiver != self.address:
            raise Exception("Only receiver can withdraw")

        accumulated = self._get_accumulated(stream)
        to_withdraw = accumulated - stream.withdrawn
        if to_withdraw <= u256(0):
            return u256(0)

        stream.withdrawn += to_withdraw
        if stream.status == "active" and stream.end_time > u256(0):
            if u256(gl.now().timestamp) >= stream.end_time:
                stream.status = "withdrawn"

        return to_withdraw

    @gl.public.view
    def get_stream(self, stream_id: str) -> dict:
        """Get stream details."""
        stream = self.streams.get(stream_id)
        if not stream:
            return {"error": "Stream not found"}
        accumulated = self._get_accumulated(stream)
        return {
            "stream_id": stream_id,
            "streamer": stream.streamer,
            "receiver": stream.receiver,
            "rate": stream.rate,
            "start_time": stream.start_time,
            "end_time": stream.end_time,
            "status": stream.status,
            "withdrawn": stream.withdrawn,
            "accumulated": accumulated,
            "available": accumulated - stream.withdrawn
        }

    @gl.public.view
    def list_streams(self, address: str) -> list:
        """List all streams for an address (as streamer or receiver)."""
        result = []
        for stream_id, stream in self.streams.items():
            if stream.streamer == address or stream.receiver == address:
                result.append(self.get_stream(stream_id))
        return result

    def _get_accumulated(self, stream: StreamState) -> u256:
        """Calculate total tokens streamed so far."""
        now_ts = u256(gl.now().timestamp)
        if stream.status == "withdrawn":
            return stream.withdrawn
        if stream.end_time > u256(0):
            if now_ts < stream.end_time:
                end = now_ts
            else:
                end = stream.end_time
        else:
            end = now_ts
        elapsed = end - stream.start_time
        if elapsed < u256(0):
            elapsed = u256(0)
        return stream.rate * elapsed
