from importlib.resources import files

from review_lens.diff import changed_files, parse_diff

SAMPLE = files("review_lens.fixtures").joinpath("sample.diff").read_text(encoding="utf-8")


def test_parses_path_and_added_line_numbers() -> None:
    parsed = parse_diff(SAMPLE)
    assert len(parsed) == 1
    fd = parsed[0]
    assert fd.path == "app/users.py"
    # The execute() call is the 5th line of the new file; the return is the 7th.
    assert 5 in fd.added_lines
    assert "db.execute" in fd.added_lines[5]
    assert 7 in fd.added_lines
    assert "return {" in fd.added_lines[7]


def test_added_lines_exclude_context_and_headers() -> None:
    fd = parse_diff(SAMPLE)[0]
    assert 1 not in fd.added_lines
    assert all(not text.startswith("+") for text in fd.added_lines.values())


def test_changed_files() -> None:
    assert changed_files(SAMPLE) == ["app/users.py"]


def test_empty_diff_is_no_files() -> None:
    assert parse_diff("") == []


def test_multi_file_diff() -> None:
    text = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+x = 1\n"
        "diff --git a/y.py b/y.py\n--- a/y.py\n+++ b/y.py\n@@ -0,0 +1 @@\n+y = 2\n"
    )
    parsed = parse_diff(text)
    assert [f.path for f in parsed] == ["x.py", "y.py"]
    assert parsed[0].added_lines == {1: "x = 1"}
    assert parsed[1].added_lines == {1: "y = 2"}


def test_deleted_file_recovers_real_path() -> None:
    text = (
        "diff --git a/gone.py b/gone.py\ndeleted file mode 100644\n"
        "--- a/gone.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-x = 1\n-y = 2\n"
    )
    assert changed_files(text) == ["gone.py"]


def test_pure_rename_registers_new_path() -> None:
    text = (
        "diff --git a/old.py b/new.py\nsimilarity index 100%\n"
        "rename from old.py\nrename to new.py\n"
    )
    assert changed_files(text) == ["new.py"]


def test_form_feed_in_content_does_not_corrupt_line_numbers() -> None:
    # \x0c (form feed) is a boundary for str.splitlines() but not for real diffs.
    text = (
        "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n"
        "@@ -0,0 +1,2 @@\n+a = '\x0cx'\n+b = 2\n"
    )
    fd = parse_diff(text)[0]
    assert fd.added_lines == {1: "a = '\x0cx'", 2: "b = 2"}


def test_crlf_diff() -> None:
    text = "diff --git a/f.py b/f.py\r\n--- a/f.py\r\n+++ b/f.py\r\n@@ -0,0 +1 @@\r\n+x = 1\r\n"
    fd = parse_diff(text)[0]
    assert fd.path == "f.py"
    assert fd.added_lines == {1: "x = 1"}
