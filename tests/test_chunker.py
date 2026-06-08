from engram.ingest.chunker import chunk_text


def _lines(n):
    return "\n".join(f"line{i}" for i in range(1, n + 1))


def test_short_file_is_one_chunk():
    chunks = chunk_text(_lines(10), lines_per_chunk=40, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 10
    assert chunks[0].text.startswith("line1")


def test_windows_with_overlap_cover_all_lines():
    chunks = chunk_text(_lines(100), lines_per_chunk=40, overlap=10)
    # step = 40 - 10 = 30 -> starts at 1, 31, 61, 91
    assert [c.line_start for c in chunks] == [1, 31, 61, 91]
    assert chunks[0].line_end == 40
    assert chunks[-1].line_end == 100  # last window clamps to EOF
    # overlap: chunk 2 starts 10 lines before chunk 1 ends
    assert chunks[1].line_start == chunks[0].line_end - 10 + 1


def test_empty_or_whitespace_file_yields_no_chunks():
    assert chunk_text("", lines_per_chunk=40, overlap=10) == []
    assert chunk_text("   \n  \n", lines_per_chunk=40, overlap=10) == []


def test_line_ranges_are_1_indexed_and_text_matches():
    chunks = chunk_text(_lines(5), lines_per_chunk=2, overlap=0)
    assert [(c.line_start, c.line_end) for c in chunks] == [(1, 2), (3, 4), (5, 5)]
    assert chunks[1].text == "line3\nline4"


def test_trailing_newline_does_not_create_empty_chunk():
    chunks = chunk_text("a\nb\n", lines_per_chunk=40, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].line_end == 2
    assert chunks[0].text == "a\nb"
