from app.security import ALLOWED, BLOCKED, MASKED, StreamFilter


def run(chunks, max_length=3000, canary=None):
    guard = StreamFilter(max_length, canary)
    shown = []
    for chunk in chunks:
        shown.append(guard.feed(chunk))
    tail, result = guard.finish()
    return guard, shown, tail, result


def pieces(text, size):
    return [text[i : i + size] for i in range(0, len(text), size)]


def test_clean_text_is_reassembled_exactly():
    text = "Hey! " * 100
    _, shown, tail, result = run(pieces(text, 7))
    assert "".join(shown) + tail == result.text == text.rstrip()
    assert result.action == ALLOWED


def test_short_reply_is_only_released_at_the_end():
    guard, shown, tail, result = run(["hello ", "there"])
    assert "".join(shown) == ""  # still inside the hold-back window
    assert tail == "hello there" and result.text == "hello there"


def test_canary_split_across_chunks_is_never_shown():
    canary = "CANARY-abc123def456"
    text = "Sure thing. " * 20 + "my marker is " + canary + " " + "more text " * 20
    guard, shown, tail, result = run(pieces(text, 5), canary=canary)
    assert guard.leaked
    assert "CANARY" not in "".join(shown)
    assert result.action == BLOCKED and result.reasons == ["system_prompt_leak"]
    assert tail == ""


def test_secret_split_across_chunks_is_redacted_before_it_is_shown():
    text = "a" * 200 + " key sk-abcdefghijklmnopqrstuvwx " + "b" * 200
    guard = StreamFilter(3000, None)
    shown_so_far = ""
    for chunk in pieces(text, 7):
        shown_so_far += guard.feed(chunk)
        assert "sk-abc" not in shown_so_far
    tail, result = guard.finish()
    full = shown_so_far + tail
    assert "[SECRET]" in full and "sk-abcdef" not in full
    assert full == result.text
    assert result.action == MASKED and "secret_redacted" in result.reasons


def test_long_replies_are_truncated():
    guard, shown, tail, result = run(pieces("x" * 400, 10), max_length=50)
    assert result.text == "x" * 50 + "..."
    assert "".join(shown) + tail == result.text
    assert result.action == MASKED and "output_truncated" in result.reasons


def test_empty_reply_is_blocked():
    _, shown, tail, result = run(["", "   "])
    assert result.action == BLOCKED and result.reasons == ["empty_output"]