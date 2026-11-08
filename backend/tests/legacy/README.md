# Legacy tests (excluded from CI)

These tests predate the current code: they import functions that no longer exist
(`get_data.handler`, `validate_parameters`) or need a running server on a fixed port.
They never ran in CI (the workflow YAML was invalid). They are kept for reference;
port the useful assertions into `tests/` before deleting them.
