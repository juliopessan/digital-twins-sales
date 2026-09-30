from digital_twins.reporting import _inline_md, parse_rewrite, split_grade


def test_split_grade_separates_letter_from_qualifier():
    assert split_grade("C — strong on X, weak on Y") == ("C", "strong on X, weak on Y")
    assert split_grade("B+") == ("B+", "")
    assert split_grade("C+ - ok") == ("C+", "ok")
    # A word that merely starts with a grade letter is not a grade.
    assert split_grade("Fair overall") == ("Fair overall", "")


def test_parse_rewrite_splits_instead_say_why():
    r = parse_rewrite("Instead of 'old line,' say: 'new line.' *Why:* it lands better.")
    assert r == {"before": "old line", "after": "new line.", "why": "it lands better."}
    r = parse_rewrite("Instead of proposing net-60, open with: 'Renewal is $520k.' *Why:* locks price.")
    assert r["before"] == "proposing net-60" and r["after"] == "Renewal is $520k."


def test_parse_rewrite_falls_back_to_raw_text():
    assert parse_rewrite("Just do better.") == {"before": "", "after": "Just do better.", "why": ""}


def test_inline_md_escapes_html_then_formats():
    assert _inline_md("**b** and *i* <script>") == "<strong>b</strong> and <em>i</em> &lt;script&gt;"
