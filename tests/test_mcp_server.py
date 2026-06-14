import importlib


def test_mcp_server_module_imports_and_exposes_app_and_main() -> None:
    server = importlib.import_module("magicreview.mcp_server.server")

    assert hasattr(server, "mcp")
    assert callable(server.main)
    assert callable(server.review_file)
    assert callable(server.review_project)
    assert callable(server.review_diff)
