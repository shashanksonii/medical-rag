from __future__ import annotations

from app.ingestion.layout import Word, words_to_lines


def w(text: str, x0: float, y0: float, x1: float, y1: float) -> Word:
    return Word(text, x0, y0, x1, y1)


def test_table_row_stays_on_one_line_with_column_gaps() -> None:
    words = [
        w("Hemoglobin", 50, 100, 120, 112),
        w("13.2", 230, 101, 260, 113),
        w("g/dL", 330, 100, 360, 112),
        w("12.0", 440, 100, 470, 112),
        w("-", 474, 100, 480, 112),
        w("16.0", 484, 100, 514, 112),
    ]
    (line,) = words_to_lines(words)
    assert line.text == "Hemoglobin  13.2  g/dL  12.0 - 16.0"


def test_normal_word_gap_is_a_single_space() -> None:
    (line,) = words_to_lines([w("Report", 50, 100, 100, 112), w("Date:", 104, 100, 140, 112)])
    assert line.text == "Report Date:"


def test_rows_sorted_top_to_bottom_regardless_of_input_order() -> None:
    lines = words_to_lines([w("second", 50, 130, 100, 142), w("first", 50, 100, 90, 112)])
    assert [line.text for line in lines] == ["first", "second"]


def test_words_ordered_left_to_right_within_row() -> None:
    (line,) = words_to_lines([w("B", 120, 100, 130, 112), w("A", 50, 100, 60, 112)])
    assert line.text.startswith("A") and line.text.endswith("B")


def test_slight_baseline_jitter_stays_in_one_row() -> None:
    words = [w("a", 50, 100, 60, 112), w("b", 70, 103, 80, 115), w("c", 90, 98, 100, 110)]
    assert len(words_to_lines(words)) == 1


def test_adjacent_text_lines_are_not_merged() -> None:
    words = [w("line1", 50, 100, 100, 112), w("line2", 50, 117, 100, 129)]
    assert len(words_to_lines(words)) == 2


def test_bbox_is_union_of_words() -> None:
    (line,) = words_to_lines([w("a", 50, 100, 60, 112), w("b", 200, 99, 230, 113)])
    assert line.bbox == (50, 99, 230, 113)


def test_empty_and_blank_words_ignored() -> None:
    assert words_to_lines([]) == []
    assert words_to_lines([w("  ", 0, 0, 5, 5)]) == []
