import unittest

from walled_ai.proxy import inspect_tool_call


class TestInspectToolCall(unittest.TestCase):

    def test_valid_tool_call(self):
        message = (
            b'{"jsonrpc":"2.0","id":15,"method":"tools/call",'
            b'"params":{"name":"read_file",'
            b'"arguments":{"path":"employees.txt"}}}'
        )

        result = inspect_tool_call(message)

        self.assertIsNotNone(result)
        assert result is not None

        self.assertEqual(result.request_id, 15)
        self.assertEqual(result.tool_name, "read_file")
        self.assertEqual(
            result.arguments,
            {"path": "employees.txt"},
        )

    def test_non_tool_call_returns_none(self):
        message = (
            b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
        )

        result = inspect_tool_call(message)

        self.assertIsNone(result)

    def test_invalid_json_returns_none(self):
        message = b"not valid json"

        result = inspect_tool_call(message)

        self.assertIsNone(result)

    def test_missing_tool_name_returns_none(self):
        message = (
            b'{"jsonrpc":"2.0","id":1,'
            b'"method":"tools/call","params":{"arguments":{}}}'
        )

        result = inspect_tool_call(message)

        self.assertIsNone(result)

    def test_invalid_arguments_returns_none(self):
        message = (
            b'{"jsonrpc":"2.0","id":1,'
            b'"method":"tools/call",'
            b'"params":{"name":"read_file",'
            b'"arguments":"invalid"}}'
        )

        result = inspect_tool_call(message)

        self.assertIsNone(result)

    def test_string_request_id(self):
        message = (
            b'{"jsonrpc":"2.0","id":"req-abc",'
            b'"method":"tools/call",'
            b'"params":{"name":"read_file",'
            b'"arguments":{"path":"employees.txt"}}}'
        )

        result = inspect_tool_call(message)

        self.assertIsNotNone(result)
        assert result is not None

        self.assertEqual(result.request_id, "req-abc")

    def test_missing_arguments_defaults_to_empty_dict(self):
        message = (
            b'{"jsonrpc":"2.0","id":2,'
            b'"method":"tools/call",'
            b'"params":{"name":"read_file"}}'
        )

        result = inspect_tool_call(message)

        self.assertIsNotNone(result)
        assert result is not None

        self.assertEqual(result.arguments, {})

    def test_boolean_request_id_returns_none(self):
        message = (
            b'{"jsonrpc":"2.0","id":true,'
            b'"method":"tools/call",'
            b'"params":{"name":"read_file","arguments":{}}}'
        )

        result = inspect_tool_call(message)

        self.assertIsNone(result)

    def test_json_array_returns_none(self):
        message = b'[1, 2, 3]'

        result = inspect_tool_call(message)

        self.assertIsNone(result)

    def test_invalid_utf8_returns_none(self):
        message = b"\xff\xfe\xfa"

        result = inspect_tool_call(message)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()