"""Tests for ``filter_requested_fields`` (no mutation, safe guards)."""

from __future__ import annotations

import copy

from CypartaGraphqlSubscriptionsTools.utils import filter_requested_fields


def test_none_or_empty_requested_fields_returns_same_object_no_mutation():
    model_payload = {"pk": 1, "fields": {"id": 1, "name": "x"}}
    original = copy.deepcopy(model_payload)
    assert filter_requested_fields(model_payload, None) is model_payload
    assert filter_requested_fields(model_payload, []) is model_payload
    assert model_payload == original


def test_non_dict_input_unchanged():
    assert filter_requested_fields("x", ["a"]) == "x"
    assert filter_requested_fields(None, ["a"]) is None


def test_dict_without_fields_key_unchanged():
    d = {"event": "custom", "meta": 1}
    assert filter_requested_fields(d, ["id"]) is d


def test_fields_not_dict_unchanged():
    d = {"pk": 1, "fields": "not-a-dict"}
    assert filter_requested_fields(d, ["id"]) is d


def test_filter_returns_new_dict_and_does_not_mutate_original():
    inp = {"pk": 1, "fields": {"id": 1, "name": "n", "secret": "s"}}
    snapshot = copy.deepcopy(inp)
    out = filter_requested_fields(inp, ["id", "name"])
    assert out is not inp
    assert out["fields"] is not inp["fields"]
    assert out["fields"] == {"id": 1, "name": "n"}
    assert inp == snapshot


def test_model_style_payload_subset():
    payload = {"pk": 42, "fields": {"id": 42, "title": "t", "body": "b"}}
    got = filter_requested_fields(payload, ["id", "title"])
    assert got["pk"] == 42
    assert got["fields"] == {"id": 42, "title": "t"}


def test_custom_dict_event_with_fields():
    event = {"type": "tick", "seq": 3, "fields": {"a": 1, "b": 2}}
    got = filter_requested_fields(event, ["b"])
    assert got["type"] == "tick"
    assert got["seq"] == 3
    assert got["fields"] == {"b": 2}
