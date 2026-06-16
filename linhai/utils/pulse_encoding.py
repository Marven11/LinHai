import math
import base64
import enum

METADATA_MAX_LENGTH = 22


class DecodeState(enum.Enum):
    WAITING_DATA = 0
    COMPOSING = 1
    COMPOSED = 2


_SAFE_BYTES = frozenset(
    b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 {}[]":,._-\\'
)


def encode(data: bytes, marker: bytes, max_length: int, text_only: bool) -> list[bytes]:
    if text_only and data and _SAFE_BYTES.issuperset(data):
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
        fractions = [
            marker + b"B" + str(len(b64)).encode() + b" " + b64 for b64 in b64s
        ]
    else:
        fractions = [marker + b"R" + str(len(b)).encode() + b" " + b for b in slices]
    return fractions + [marker + b"X1 ;"]


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
                if len(stream) <= len(self.marker):
                    break
                pos = stream.find(self.marker)
                if pos != -1:
                    stream = stream[pos + len(self.marker) :]
                    self.is_waiting_marker = False
                else:
                    stream = stream[-len(self.marker) :]
                    break
            else:
                state, decoded, remains = decode(stream)
                stream = remains
                self.composing += decoded
                if state == DecodeState.COMPOSED:
                    self.composed.append(self.composing)
                    self.composing = b""

                if state == DecodeState.WAITING_DATA:
                    break
                else:
                    self.is_waiting_marker = True

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
    import secrets

    marker = secrets.token_bytes(16)

    enc = PulseEncoder(marker, 32, True)
    fractions = enc.encode(
        json.dumps({"name": "litiansuo", "age": 24, "id": 1145141919810}).encode()
    )

    mixed = [b for fraction in fractions for b in [secrets.token_bytes(128), fraction]]

    sent = []
    buffer = b""
    for b in mixed:
        buffer += b
        if len(buffer) > 150:
            sent.append(buffer[:150])
            buffer = buffer[150:]
    sent.append(buffer)

    dec = PulseDecoder(marker)
    for b in sent:
        dec.comsume(b)
        for composed in dec.emit_composed():
            print(f"{composed=}")


if __name__ == "__main__":
    example()
