import json

from app.reviewer import ReviewService
from magicreview.mcp_server import tools


class FakeService:
    def review_file(self, path: str):
        return {"issues": [{"severity": "low", "type": "Fake", "file": path, "line": 1, "message": "ok", "suggestion": "ok"}]}

    def review_project(self, path: str):
        return {"issues": [{"severity": "low", "type": "FakeProject", "file": path, "line": 1, "message": "ok", "suggestion": "ok"}]}

    def review_diff(self, diff: str):
        return {"issues": [{"severity": "low", "type": "FakeDiff", "file": "<diff>", "line": 1, "message": diff, "suggestion": "ok"}]}


def test_mcp_tools_call_review_service_and_return_json_serializable_dict() -> None:
    tools.set_review_service(FakeService())

    file_result = tools.review_file("a.py")
    project_result = tools.review_project(".")
    diff_result = tools.review_diff("diff")

    assert file_result["issues"][0]["type"] == "Fake"
    assert project_result["issues"][0]["type"] == "FakeProject"
    assert diff_result["issues"][0]["type"] == "FakeDiff"
    json.dumps(file_result)
    json.dumps(project_result)
    json.dumps(diff_result)
    tools.set_review_service(ReviewService())
