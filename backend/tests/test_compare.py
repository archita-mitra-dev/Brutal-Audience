from app.analysis.compare import align, compare
from app.analysis.stats import analyse

from .test_analysis import full


def segs(*texts):
    return [{"id": i, "label": f"Paragraph {i}", "text": t} for i, t in enumerate(texts, start=1)]


def A(scores, n):
    return analyse("x", "completed", segs(*[f"s{i}" for i in range(1, n + 1)]), full(scores), 4 * n)


def row(*s):
    return dict(zip(("doom", "critic", "fan", "newbie"), s))


# ---- alignment ----------------------------------------------------------------------------
def test_unchanged_edited_new_removed():
    base = segs("The lighthouse had been dark for eleven years.", "Mara arrived on the ferry with one suitcase.", "She never opened the letter.")
    rev = segs("The lighthouse had been dark for eleven years.", "Mara arrived on the ferry with a single battered suitcase.", "A brand new scene about a dog barking at the sea.")
    got = align(base, rev)
    kinds = [(b, r, c) for b, r, c in got]
    assert kinds[0] == (1, 1, "unchanged")
    assert (2, 2, "edited") in kinds
    assert (None, 3, "new") in kinds and (3, None, "removed") in kinds


def test_identical_works_align_one_to_one():
    t = segs("a one", "b two", "c three")
    assert align(t, t) == [(1, 1, "unchanged"), (2, 2, "unchanged"), (3, 3, "unchanged")]


def test_inserted_paragraph_shifts_ids_but_matches_text():
    base = segs("alpha alpha alpha", "bravo bravo bravo")
    rev = segs("alpha alpha alpha", "INSERTED completely different words here", "bravo bravo bravo")
    got = align(base, rev)
    assert (2, 3, "unchanged") in got and (None, 2, "new") in got


# ---- comparison -----------------------------------------------------------------------------
BASE = {1: row((3, True), (5, True), (6, True), (5, True)),
        2: row((2, False), (5, True), (6, True), (5, True))}
BASE = {k: dict(zip(("doom", "critic", "fan", "newbie"), v)) for k, v in
        {1: ((3, True), (5, True), (6, True), (5, True)), 2: ((2, False), (5, True), (6, True), (5, True))}.items()}


def mk(vals):
    return {k: dict(zip(("doom", "critic", "fan", "newbie"), v)) for k, v in vals.items()}


def test_improvement_resolution_and_headline():
    b = A(mk({1: ((3, True), (5, True), (6, True), (5, True)), 2: ((2, False), (5, True), (6, True), (5, True))}), 2)
    r = A(mk({1: ((7, True), (5, True), (6, True), (5, True)), 2: ((6, True), (5, True), (6, True), (5, True))}), 2)
    c = compare(baseline=b, base_segments=segs("s1", "s2"), revised=r, rev_segments=segs("s1", "s2"),
                baseline_run_id="b", run_id="r", kind="revision", label=None)
    assert c.overall_delta > 0 and c.verdict == "better" and c.improved == 2
    s1 = c.segments[0]
    assert s1.personas["doom"].before == 3 and s1.personas["doom"].after == 7
    assert [o.status for o in c.dropoffs] == ["resolved"] and "no longer wants to stop" in c.dropoffs[0].text
    assert any("Doomscroller responded better to Paragraph 1: 3/10 became 7/10" in h for h in c.highlights)


def test_unchanged_text_that_got_worse_is_collateral():
    b = A(mk({1: ((6, True),) * 4, 2: ((6, True),) * 4}), 2)
    r = A(mk({1: ((6, True),) * 4, 2: ((3, True),) * 4}), 2)
    c = compare(baseline=b, base_segments=segs("s1", "s2"), revised=r, rev_segments=segs("s1", "s2"),
                baseline_run_id="b", run_id="r", kind="whatif", label="what if")
    assert c.segments[1].collateral and c.collateral == 1 and c.verdict == "worse"
    assert any("not edited" in h for h in c.highlights)


def test_edited_text_that_got_worse_is_not_collateral():
    b = A(mk({1: ((6, True),) * 4}), 1)
    r = A(mk({1: ((3, True),) * 4}), 1)
    c = compare(baseline=b, base_segments=segs("old words here"), revised=r, rev_segments=segs("old words there"),
                baseline_run_id="b", run_id="r", kind="revision", label=None)
    assert c.segments[0].change == "edited" and not c.segments[0].collateral


def test_still_stopping_and_new_drop_offs():
    b = A(mk({1: ((6, True), (6, True), (6, True), (6, True)), 2: ((2, False),) + ((6, True),) * 3}), 2)
    r = A(mk({1: ((6, True), (2, False), (6, True), (6, True)), 2: ((2, False),) + ((6, True),) * 3}), 2)
    c = compare(baseline=b, base_segments=segs("s1", "s2"), revised=r, rev_segments=segs("s1", "s2"),
                baseline_run_id="b", run_id="r", kind="revision", label=None)
    by = {o.persona: o.status for o in c.dropoffs}
    assert by == {"doom": "still", "critic": "new"}


def test_small_differences_are_not_improvements():
    b = A(mk({1: ((6, True),) * 4}), 1)
    r = A(mk({1: ((6, True), (6, True), (6, True), (7, True))}), 1)
    c = compare(baseline=b, base_segments=segs("s1"), revised=r, rev_segments=segs("s1"),
                baseline_run_id="b", run_id="r", kind="revision", label=None)
    assert c.improved == 0 and c.segments[0].status == "unchanged"


def test_noise_note_is_always_present():
    b = A(mk({1: ((6, True),) * 4}), 1)
    c = compare(baseline=b, base_segments=segs("s1"), revised=b, rev_segments=segs("s1"),
                baseline_run_id="b", run_id="r", kind="whatif", label="x")
    assert "not a guaranteed improvement" in c.noise_note and c.verdict == "about_the_same"
