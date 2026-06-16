import json
from unittest import TestCase

from linhai.utils.pulse_encoding import (
    PulseEncoder,
    PulseDecoder,
    encode,
    _SAFE_BYTES,
)


class TestPulseEncoding(TestCase):
    def test_text_only_default_uses_base64_for_unsafe_data(self):
        marker = b"<test>"
        enc = PulseEncoder(marker, 3000, True)
        data = b"hello\x00world"
        fractions = enc.encode(data)
        self.assertTrue(
            any(b"B" in f for f in fractions),
            "Unsafe data should use base64 B frames",
        )

    def test_text_only_uses_raw_for_safe_json_data(self):
        marker = b"<test>"
        enc = PulseEncoder(marker, 3000, True)
        data = json.dumps({"key": "value", "num": 123}).encode()
        fractions = enc.encode(data)
        self.assertTrue(
            all(b"R" in f or b"X" in f for f in fractions),
            "Safe JSON data should use raw R frames",
        )

    def test_text_only_uses_base64_for_data_with_newlines(self):
        marker = b"<test>"
        enc = PulseEncoder(marker, 3000, True)
        data = json.dumps({"text": "safe"}).encode() + b"\x00"
        fractions = enc.encode(data)
        self.assertTrue(
            any(b"B" in f for f in fractions),
            "Data with null byte should use base64 B frames",
        )

    def test_roundtrip_text_only_safe_json(self):
        marker = b"<test>"
        enc = PulseEncoder(marker, 3000, True)
        original = json.dumps(
            {"jsonrpc": "2.0", "id": "1", "method": "ping", "params": {}}
        ).encode()
        fractions = enc.encode(original)
        dec = PulseDecoder(marker)
        for f in fractions:
            dec.comsume(f)
        results = dec.emit_composed()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], original)

    def test_roundtrip_text_only_unsafe_data(self):
        marker = b"<test>"
        enc = PulseEncoder(marker, 3000, True)
        original = json.dumps({"text": "hello\nworld\t!"}).encode()
        fractions = enc.encode(original)
        dec = PulseDecoder(marker)
        for f in fractions:
            dec.comsume(f)
        results = dec.emit_composed()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], original)

    def test_safe_bytes_contains_expected_chars(self):
        expected = set(
            b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 {}[]":,._-\\'
        )
        self.assertEqual(_SAFE_BYTES, frozenset(expected))

    def test_encode_text_only_false_always_raw(self):
        marker = b"<test>"
        enc = PulseEncoder(marker, 3000, False)
        data = b"any\x01binary\xffdata"
        fractions = enc.encode(data)
        self.assertTrue(
            all(b"R" in f or b"X" in f for f in fractions),
            "text_only=False should always use raw R frames",
        )

    def test_encode_safe_data_preserves_content(self):
        marker = b"<m>"
        data = b'{"a":1,"b":[2,3]}'
        fractions = encode(data, marker, 3000, True)
        dec = PulseDecoder(marker)
        for f in fractions:
            dec.comsume(f)
        results = dec.emit_composed()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], data)
