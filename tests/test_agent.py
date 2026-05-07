from unittest.mock import MagicMock

from oracle.agent import Agent


def _stop_message(text: str):
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text=text)]
    return msg


def _tool_use_message(tool_name: str, tool_input: dict, tool_use_id: str = "call_1"):
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    tool_block = MagicMock(type="tool_use", id=tool_use_id, input=tool_input)
    tool_block.name = tool_name  # set after construction; MagicMock treats 'name' specially
    msg.content = [
        MagicMock(type="text", text="thinking"),
        tool_block,
    ]
    return msg


def test_agent_returns_text_when_no_tools_called():
    client = MagicMock()
    client.messages.create.return_value = _stop_message("the answer is 42")
    agent = Agent(client=client, tool_runner=lambda name, args: {})
    out = agent.ask("what is 6 times 7?")
    assert "42" in out


def test_agent_runs_tool_then_finalizes():
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_message("get_schema", {"table": "raw.users"}),
        _stop_message("the table has 2 columns"),
    ]
    runner_calls = []

    def runner(name, args):
        runner_calls.append((name, args))
        return {"columns": [{"name": "a"}, {"name": "b"}]}

    agent = Agent(client=client, tool_runner=runner)
    out = agent.ask("schema of raw.users?")

    assert "2 columns" in out
    assert runner_calls == [("get_schema", {"table": "raw.users"})]


def test_agent_caps_tool_calls():
    client = MagicMock()
    # always returns a tool_use — would loop forever without cap
    client.messages.create.return_value = _tool_use_message("get_schema", {"table": "x"})
    agent = Agent(client=client, tool_runner=lambda n, a: {}, max_tool_calls=3)
    out = agent.ask("trick question")
    assert "couldn't answer" in out.lower() or "could not" in out.lower()
