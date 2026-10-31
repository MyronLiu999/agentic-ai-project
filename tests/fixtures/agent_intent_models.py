"""Free model responses for the router's bounded intent classification."""

from harness.client import Usage


class StatusIntent:
    free = True
    answer = "status_question"

    def __init__(self, settings=None):
        self.requests = []

    def create(self, *, system, messages, tools):
        self.requests.append({"system": system, "messages": messages, "tools": tools})
        return [{"type": "text", "text": self.answer}], "end_turn", "says-done", Usage(20, 5)


class NewTaskIntent(StatusIntent):
    answer = "new_task"


class InvalidIntent(StatusIntent):
    answer = "Done."


class ToolCallingIntent(StatusIntent):
    def create(self, *, system, messages, tools):
        return [{"type": "text", "text": "new_task"},
                {"type": "tool_use", "id": "unexpected", "name": "save_report", "input": {}}], \
            "tool_use", "says-done", Usage(20, 5)
