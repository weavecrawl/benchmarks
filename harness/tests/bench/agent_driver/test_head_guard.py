"""The head guard of the agent driver: the benches' agent may touch bench-server.b and nothing else (the default head is a person's own Chrome)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from head_guard import PREFIX as T, decide  # noqa: E402


def test_a_call_on_the_server_head_passes():
    assert decide(T + "goto", {"url": "https://example.com", "head": "bench-server.b"})[0]


def test_a_call_with_no_head_is_refused():
    ok, why = decide(T + "goto", {"url": "https://example.com"})
    assert not ok and "head" in why


def test_a_call_on_a_persons_chrome_is_refused():
    assert not decide(T + "read", {"url": "https://example.com", "head": "mac.a"})[0]


def test_a_head_that_only_starts_with_the_name_is_refused():
    assert not decide(T + "read", {"head": "bench-server.b.evil"})[0]
    assert not decide(T + "read", {"head": "wcb.b"})[0]


def test_session_open_must_name_the_server_head():
    assert decide(T + "session", {"action": "open", "on": "bench-server/b"})[0]
    assert not decide(T + "session", {"action": "open"})[0]
    assert not decide(T + "session", {"action": "open", "on": "mac/a"})[0]


def test_a_tool_of_another_server_is_not_judged():
    assert decide("Bash", {"command": "ls"})[0]


def test_ask_human_is_refused_even_on_the_server_head():
    """It would send a notice to a person's devices."""
    ok, why = decide(T + "ask_human", {"reason": "x", "head": "bench-server.b"})
    assert not ok and "ask_human" in why
