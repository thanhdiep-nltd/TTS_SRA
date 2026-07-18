"""Test point ID idempotent."""

from edu_pipeline.hashing import content_point_id


def test_same_text_same_id():
    text = "Định lý Pytago: a^2 + b^2 = c^2"
    assert content_point_id(text) == content_point_id(text)


def test_whitespace_normalized():
    assert content_point_id("a  b\nc") == content_point_id("a b c")


def test_different_text_different_id():
    assert content_point_id("Bài 1") != content_point_id("Bài 2")


def test_returns_valid_uuid():
    import uuid

    uuid.UUID(content_point_id("kiểm tra"))  # không raise nghĩa là hợp lệ
