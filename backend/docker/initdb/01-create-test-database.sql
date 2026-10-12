-- Runs once, when the local Docker volume is first created (see compose.yaml).
-- A second, separate database for the test suite, so running `uv run pytest`
-- never touches the data you use while clicking around the app locally.
CREATE DATABASE schoolflow_test OWNER schoolflow_owner;
