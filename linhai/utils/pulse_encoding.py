import math
import base64
import enum

METADATA_MAX_LENGTH = 22


class DecodeState(enum.Enum):
    WAITING_DATA = 0
    COMPOSING = 1
    COMPOSED = 2


def encode(data: bytes, marker: bytes, max_length: int, text_only: bool) -> bytes:
    if data.isascii() and data.decode("ascii").isprintable():
        text_only = False
    assert max_length > METADATA_MAX_LENGTH
    step = (
        max_length - METADATA_MAX_LENGTH
        if not text_only
        else math.floor((max_length - 3) / 4 * 3) - METADATA_MAX_LENGTH
    )
    slices = [data[i : i + step] for i in range(0, len(data), step)]
    if text_only:
        b64s = (base64.b64encode(b) for b in slices)
        fractions = [b"B" + str(len(b64)).encode() + b" " + b64 for b64 in b64s] + [
            b"X1 ;"
        ]
    else:
        fractions = [b"R" + str(len(b)).encode() + b" " + b for b in slices] + [b"X1 ;"]
    return marker + b"".join(fractions)


def decode(fraction: bytes) -> tuple[DecodeState, bytes, bytes]:
    if len(fraction) <= METADATA_MAX_LENGTH and b" " not in fraction:
        return DecodeState.WAITING_DATA, b"", fraction

    metadata, data = fraction.split(b" ", maxsplit=1)
    action, length_str = metadata[0:1], metadata[1:].decode("ascii")
    if not length_str:
        return DecodeState.WAITING_DATA, b"", fraction
    length = int(length_str)
    if len(data) < length:
        return DecodeState.WAITING_DATA, b"", fraction
    if action == b"R":
        return DecodeState.COMPOSING, data[:length], data[length:]
    if action == b"B":
        return DecodeState.COMPOSING, base64.b64decode(data[:length]), data[length:]
    if action == b"X":
        return DecodeState.COMPOSED, b"", data[length:]
    else:
        raise RuntimeError(f"Malformed data: {metadata=} {data=} ")


class PulseDecoder:
    def __init__(self, marker: bytes):
        self.is_waiting_marker = True
        self.marker = marker
        self.composed: list[bytes] = []
        self.composing = b""
        self.stream_remains = b""

    def comsume(self, stream: bytes):
        stream = self.stream_remains + stream
        while stream:
            if self.is_waiting_marker:
                if len(stream) <= len(self.marker) * 2:
                    break
                pos = stream.find(self.marker)
                if pos != -1:
                    stream = stream[pos + len(self.marker) :]
                    self.is_waiting_marker = False
                else:
                    stream = b""
            else:
                state, decoded, remains = decode(stream)
                stream = remains
                self.composing += decoded
                if state == DecodeState.COMPOSED:
                    self.composed.append(self.composing)
                    self.composing = b""
                    self.is_waiting_marker = True
                if state == DecodeState.WAITING_DATA:
                    break
        self.stream_remains = stream

    def emit_composed(self):
        result = self.composed
        self.composed = []
        return result


class PulseEncoder:
    def __init__(self, marker: bytes, max_length: int, text_only: bool):
        self.marker = marker
        self.max_length = max_length
        self.text_only = text_only

    def encode(self, data: bytes):
        return encode(data, self.marker, self.max_length, self.text_only)


def example():
    import json

    enc = PulseEncoder(b"<should_be_random>", 32, True)
    mixed = (
        b"111"
        + enc.encode(json.dumps({"name": "litiansuo", "age": 24, "id": 1145141919810}).encode())
        + b"222"
        + enc.encode(b"litiansuo")
        + b"333"
    )
    dec = PulseDecoder(b"<should_be_random>")
    for i in range(0, len(mixed), 10):
        dec.comsume(mixed[i : i + 10])
        for composed in dec.emit_composed():
            print(f"{composed=}")


if __name__ == "__main__":
    example()
