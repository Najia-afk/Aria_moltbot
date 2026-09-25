"""Tests for unwrap_json_message_envelope, shared by LLMGateway.complete()
and the WebSocket streaming path in aria_engine/streaming.py.

Some free-tier models (observed on nvidia/nemotron-3.5-lightning:free) leak a
stray {"message": "...", "user_name": "..."} JSON envelope as their entire
reply instead of plain text, under heavy tool-calling context. This was first
fixed for the non-streaming complete() path; streaming() had no equivalent
cleanup, so the raw JSON was displayed (and persisted) verbatim in the live
chat UI. This suite locks down the shared unwrap function's behavior so
regressions in either call site are caught.
"""
from aria_engine.llm_gateway import unwrap_json_message_envelope


def test_unwraps_simple_message_envelope():
    raw = '{"message": "Hello! How can I assist you today?", "user_name": "user"}'
    assert unwrap_json_message_envelope(raw) == "Hello! How can I assist you today?"


def test_unwraps_envelope_with_surrounding_whitespace():
    raw = '  \n{"message": "All good"}\n  '
    assert unwrap_json_message_envelope(raw) == "All good"


def test_plain_text_passes_through_unchanged():
    raw = "Hello"
    assert unwrap_json_message_envelope(raw) == raw


def test_json_without_message_field_passes_through_unchanged():
    raw = '{"result": "ok", "count": 3}'
    assert unwrap_json_message_envelope(raw) == raw


def test_message_field_not_a_string_passes_through_unchanged():
    raw = '{"message": {"nested": true}}'
    assert unwrap_json_message_envelope(raw) == raw


def test_invalid_json_passes_through_unchanged():
    raw = '{"message": "unterminated'
    assert unwrap_json_message_envelope(raw) == raw


def test_embedded_json_inside_prose_is_not_touched():
    raw = 'Here is the config: {"message": "hi"} — hope that helps.'
    assert unwrap_json_message_envelope(raw) == raw


def test_empty_string_passes_through_unchanged():
    assert unwrap_json_message_envelope("") == ""
