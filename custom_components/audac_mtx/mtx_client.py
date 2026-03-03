"""TCP client for communicating with the Audac MTX device."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .const import DEFAULT_PORT, DEFAULT_SOURCE, INPUT_NAMES, BASS_TREBLE_MAP

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 1
RECONNECT_DELAY = 1.0
INTER_COMMAND_DELAY = 0.12
MAX_READ_LINES = 10


class MTXClient:
    def __init__(self, host: str, port: int = DEFAULT_PORT, source: str = DEFAULT_SOURCE) -> None:
        self._host = host
        self._port = port
        self._source = source
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._consecutive_failures = 0

    @property
    def host(self) -> str:
        return self._host

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> None:
        if self._writer is not None:
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=5,
            )
            self._consecutive_failures = 0
            _LOGGER.debug("Connected to MTX at %s:%s", self._host, self._port)
            await asyncio.sleep(0.2)
            await self._drain_buffer()
        except Exception as err:
            self._reader = None
            self._writer = None
            raise ConnectionError(f"Cannot connect to MTX at {self._host}:{self._port}: {err}") from err

    async def disconnect(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
            _LOGGER.debug("Disconnected from MTX")

    async def _ensure_connected(self) -> None:
        if self._writer is None:
            if self._consecutive_failures > 0:
                delay = min(RECONNECT_DELAY * self._consecutive_failures, 10.0)
                await asyncio.sleep(delay)
            await self.connect()

    async def _drain_buffer(self) -> None:
        if self._reader is None:
            return
        drained = 0
        while True:
            try:
                data = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=0.05,
                )
                if data == b"":
                    break
                drained += 1
                if drained > 50:
                    break
            except asyncio.TimeoutError:
                break
        if drained:
            _LOGGER.debug("Drained %d stale lines from buffer", drained)

    def _build_command(self, command: str, argument: str = "0") -> bytes:
        return f"#|X001|{self._source}|{command}|{argument}|U|\r\n".encode()

    async def _read_response(self, command: str, timeout: float = 2.0) -> str:
        deadline = asyncio.get_event_loop().time() + timeout
        lines_read = 0
        first_protocol_line = None

        while lines_read < MAX_READ_LINES:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                line_bytes = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=min(remaining, 1.5),
                )
                line = line_bytes.decode(errors="replace").strip()
                lines_read += 1

                if not line:
                    if line_bytes == b"":
                        _LOGGER.debug("EOF received from MTX")
                        break
                    continue

                if not line.startswith("#|"):
                    continue

                _LOGGER.debug("MTX raw response: %s", line[:120])

                if first_protocol_line is None:
                    first_protocol_line = line

                parts = line.split("|")
                if len(parts) >= 4:
                    resp_cmd = parts[3]
                    if command in resp_cmd or resp_cmd.lstrip("+").startswith(command[:3]):
                        return line

            except asyncio.TimeoutError:
                break

        if first_protocol_line:
            _LOGGER.debug("No exact match for %s, using first protocol line: %s", command, first_protocol_line[:100])
            return first_protocol_line

        return ""

    async def _send_and_receive(self, command: str, argument: str = "0", retries: int = MAX_RETRIES) -> str:
        async with self._lock:
            for attempt in range(retries + 1):
                try:
                    await self._ensure_connected()
                except ConnectionError:
                    if attempt < retries:
                        self._consecutive_failures += 1
                        continue
                    raise

                raw = self._build_command(command, argument)
                try:
                    self._writer.write(raw)
                    await self._writer.drain()

                    response = await self._read_response(command, timeout=2.0)

                    if not response:
                        _LOGGER.debug("No response for command %s, attempt %d", command, attempt)
                        if attempt < retries:
                            await self.disconnect()
                            continue
                        return ""

                    self._consecutive_failures = 0
                    return response

                except (asyncio.TimeoutError, OSError, ConnectionError) as err:
                    _LOGGER.warning("Communication error with MTX for command %s (attempt %d): %s", command, attempt, err)
                    await self.disconnect()
                    self._consecutive_failures += 1
                    if attempt < retries:
                        continue
                    raise ConnectionError(f"Lost connection to MTX: {err}") from err

        return ""

    @staticmethod
    def _parse_response(response: str) -> str | None:
        if not response:
            return None
        parts = response.split("|")
        if len(parts) >= 5:
            return parts[4]
        return None

    @staticmethod
    def _is_success(response: str) -> bool:
        if not response:
            return False
        parts = response.split("|")
        return len(parts) >= 4 and "+" in parts[3]

    async def get_zone_info(self, zone: int) -> dict[str, Any]:
        command = f"GZI0{zone}"
        resp = await self._send_and_receive(command)

        data = self._parse_response(resp)
        if data is None:
            _LOGGER.debug("No parseable data for zone %d, raw response: %s", zone, resp[:100] if resp else "(empty)")
            return {}

        values = data.split("^")
        if len(values) < 5:
            _LOGGER.warning("Unexpected zone info format for zone %d: %s (expected at least 5 fields, got %d)", zone, data, len(values))
            return {}

        try:
            volume_raw = int(values[0])
            routing = int(values[1])
            mute_raw = int(values[2])
            bass_raw = int(values[3])
            treble_raw = int(values[4])
        except (ValueError, IndexError) as err:
            _LOGGER.warning("Failed to parse zone %d data '%s': %s", zone, data, err)
            return {}

        mute = mute_raw != 0

        _LOGGER.debug(
            "Zone %d: vol=%d routing=%d mute=%d(%s) bass=%d treble=%d raw='%s'",
            zone, volume_raw, routing, mute_raw, mute, bass_raw, treble_raw, data[:60],
        )

        result = {
            "volume": volume_raw,
            "volume_db": -volume_raw,
            "routing": routing,
            "source_name": INPUT_NAMES.get(routing, f"Input {routing}"),
            "mute": mute,
            "bass": bass_raw,
            "bass_db": BASS_TREBLE_MAP.get(bass_raw, 0),
            "treble": treble_raw,
            "treble_db": BASS_TREBLE_MAP.get(treble_raw, 0),
        }

        if len(values) > 5:
            remote_inputs = values[5:]
            result["remote_inputs"] = remote_inputs

        return result

    async def get_all_zones(self, zones_count: int = 8) -> dict[int, dict[str, Any]]:
        zones = {}
        for zone in range(1, zones_count + 1):
            try:
                info = await self.get_zone_info(zone)
                if info:
                    zones[zone] = info
            except ConnectionError:
                raise
            except Exception as err:
                _LOGGER.warning("Failed to get info for zone %d: %s", zone, err)
            await asyncio.sleep(INTER_COMMAND_DELAY)
        return zones

    async def set_volume(self, zone: int, volume: int) -> bool:
        volume = max(0, min(70, volume))
        resp = await self._send_and_receive(f"SV{zone}", str(volume))
        return self._is_success(resp)

    async def set_volume_up(self, zone: int) -> bool:
        resp = await self._send_and_receive(f"SVU0{zone}")
        return self._is_success(resp)

    async def set_volume_down(self, zone: int) -> bool:
        resp = await self._send_and_receive(f"SVD0{zone}")
        return self._is_success(resp)

    async def set_routing(self, zone: int, input_id: int) -> bool:
        resp = await self._send_and_receive(f"SR{zone}", str(input_id))
        return self._is_success(resp)

    async def set_bass(self, zone: int, bass: int) -> bool:
        bass = max(0, min(14, bass))
        resp = await self._send_and_receive(f"SB0{zone}", str(bass))
        return self._is_success(resp)

    async def set_treble(self, zone: int, treble: int) -> bool:
        treble = max(0, min(14, treble))
        resp = await self._send_and_receive(f"ST0{zone}", str(treble))
        return self._is_success(resp)

    async def set_mute(self, zone: int, mute: bool) -> bool:
        resp = await self._send_and_receive(f"SM0{zone}", "1" if mute else "0")
        return self._is_success(resp)

    async def save(self) -> bool:
        resp = await self._send_and_receive("SAVE")
        return self._is_success(resp)

    async def get_version(self) -> str:
        resp = await self._send_and_receive("GSV")
        data = self._parse_response(resp)
        return data or "Unknown"
