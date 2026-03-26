"""Minimal protobuf wire-format decoder for Google Play FDFE responses.

No external dependencies — decodes varint, fixed32/64, length-delimited,
and proto2 GROUP wire types directly from raw bytes.
"""

from __future__ import annotations

import struct
from typing import Any

WIRETYPE_VARINT = 0
WIRETYPE_FIXED64 = 1
WIRETYPE_LENGTH_DELIMITED = 2
WIRETYPE_START_GROUP = 3
WIRETYPE_END_GROUP = 4
WIRETYPE_FIXED32 = 5


class ProtoDecoder:

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.end = len(data)

    def _read_varint(self) -> int:
        result = 0
        shift = 0
        while True:
            if self.pos >= self.end:
                raise EOFError("Unexpected end of data while reading varint")
            b = self.data[self.pos]
            self.pos += 1
            result |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                return result
            shift += 7
            if shift >= 64:
                raise ValueError("Varint too long")

    def read_tag(self) -> tuple[int | None, int | None]:
        if self.pos >= self.end:
            return None, None
        tag = self._read_varint()
        return (tag >> 3), (tag & 0x7)

    def _read_group(self, field_number: int) -> bytes:
        start_pos = self.pos
        while self.pos < self.end:
            tag_start = self.pos
            tag = self._read_varint()
            fn = tag >> 3
            wt = tag & 0x7
            if wt == WIRETYPE_END_GROUP and fn == field_number:
                return self.data[start_pos:tag_start]
            self._skip_value(wt, field_number_for_group=fn)
        raise EOFError("Unexpected end while reading group")

    def _skip_value(self, wire_type: int, *, field_number_for_group: int | None = None) -> None:
        if wire_type == WIRETYPE_VARINT:
            self._read_varint()
        elif wire_type == WIRETYPE_FIXED64:
            self.pos += 8
        elif wire_type == WIRETYPE_LENGTH_DELIMITED:
            self.pos += self._read_varint()
        elif wire_type == WIRETYPE_FIXED32:
            self.pos += 4
        elif wire_type == WIRETYPE_START_GROUP:
            if field_number_for_group is None:
                raise ValueError("Missing field number for group")
            self._read_group(field_number_for_group)
        elif wire_type == WIRETYPE_END_GROUP:
            return
        else:
            raise ValueError(f"Unknown wire type: {wire_type}")

    def read_field(self) -> tuple[int | None, int | None, Any]:
        fn, wt = self.read_tag()
        if fn is None:
            return None, None, None

        if wt == WIRETYPE_VARINT:
            v = self._read_varint()
        elif wt == WIRETYPE_FIXED64:
            if self.pos + 8 > self.end:
                raise EOFError("Unexpected end")
            v = struct.unpack("<Q", self.data[self.pos : self.pos + 8])[0]
            self.pos += 8
        elif wt == WIRETYPE_LENGTH_DELIMITED:
            ln = self._read_varint()
            if self.pos + ln > self.end:
                raise EOFError("Unexpected end")
            v = self.data[self.pos : self.pos + ln]
            self.pos += ln
        elif wt == WIRETYPE_FIXED32:
            if self.pos + 4 > self.end:
                raise EOFError("Unexpected end")
            v = struct.unpack("<I", self.data[self.pos : self.pos + 4])[0]
            self.pos += 4
        elif wt == WIRETYPE_START_GROUP:
            v = self._read_group(fn)
        else:
            raise ValueError(f"Unknown wire type: {wt}")

        return fn, wt, v

    def read_all_ordered(self) -> list[tuple[int, int, Any]]:
        out: list[tuple[int, int, Any]] = []
        while self.pos < self.end:
            fn, wt, v = self.read_field()
            if fn is None:
                break
            out.append((fn, wt, v))
        return out

    @staticmethod
    def decode_string(b: bytes) -> str:
        try:
            return b.decode("utf-8")
        except Exception:
            return b.decode("latin-1", errors="replace")


def extract_strings(data: bytes) -> list[str]:
    """Pull all UTF-8 strings from a protobuf blob (non-recursive, fast)."""
    out: list[str] = []
    try:
        for _fn, wt, v in ProtoDecoder(data).read_all_ordered():
            if wt == WIRETYPE_LENGTH_DELIMITED and isinstance(v, (bytes, bytearray)):
                try:
                    s = v.decode("utf-8")
                    if s.isprintable() or "\n" in s:
                        out.append(s)
                except UnicodeDecodeError:
                    out.extend(extract_strings(v))
    except Exception:
        pass
    return out
