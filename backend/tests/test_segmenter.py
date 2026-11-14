from app.schemas import ContentType
from app.segmenter import segment_content

STORY = (
    "The lighthouse had been dark for eleven years, and nobody in Port Ellery "
    "talked about why.\n\n"
    "Mara arrived on the morning ferry with one suitcase and a letter she had "
    "not yet decided to open.\n\n"
    "Hi.\n\n"
    "The keeper's cottage smelled of salt and old paper. She set the suitcase "
    "down and listened to the sea breathe."
)

SCREENPLAY = """INT. LIGHTHOUSE - NIGHT

Wind howls. MARA climbs the spiral stairs, lantern shaking.

MARA
Hello? Is anyone up here?

EXT. HARBOR - DAWN

Fishing boats rock in fog. An OLD MAN watches from the pier.
"""

LYRICS = """I left my heart in a rented room
Paid the rent in silver moons

Now the morning's coming through
And I'm still singing about you
"""


def _assert_exact(content, segments):
    for s in segments:
        assert content[s.char_start:s.char_end] == s.text
    ids = [s.id for s in segments]
    assert ids == list(range(1, len(ids) + 1))


def test_story_paragraphs_and_exact_slices():
    segs, truncated = segment_content(STORY, ContentType.story)
    _assert_exact(STORY, segs)
    assert not truncated
    # "Hi." is a tiny fragment and is merged into the next paragraph
    assert len(segs) == 3
    assert segs[2].text.startswith("Hi.")


def test_order_is_preserved():
    segs, _ = segment_content(STORY, ContentType.story)
    starts = [s.char_start for s in segs]
    assert starts == sorted(starts)


def test_screenplay_splits_on_sluglines():
    segs, _ = segment_content(SCREENPLAY, ContentType.screenplay)
    _assert_exact(SCREENPLAY, segs)
    assert len(segs) == 2
    assert segs[0].text.startswith("INT. LIGHTHOUSE")
    assert segs[1].text.startswith("EXT. HARBOR")
    assert segs[0].label == "Scene 1"


def test_screenplay_without_sluglines_falls_back_to_blocks():
    text = "MARA\nWe should go now, before the tide turns and we lose the path.\n\nJON\nNot yet. I need to see it once more, just once."
    segs, _ = segment_content(text, ContentType.screenplay)
    _assert_exact(text, segs)
    assert len(segs) == 2


def test_lyrics_by_stanza():
    segs, _ = segment_content(LYRICS, ContentType.lyrics)
    _assert_exact(LYRICS, segs)
    assert len(segs) == 2
    assert segs[0].label == "Stanza 1"


def test_lyrics_single_block_grouped_by_lines():
    text = "\n".join(f"line number {i} of the song" for i in range(1, 10))
    segs, _ = segment_content(text, ContentType.lyrics)
    _assert_exact(text, segs)
    assert len(segs) == 3  # 4 + 4 + 1


def test_long_paragraph_is_split_on_sentences():
    sentence = "This sentence is a perfectly ordinary one that goes on a bit. "
    text = sentence * 60
    segs, _ = segment_content(text, ContentType.article)
    _assert_exact(text, segs)
    assert len(segs) > 1
    assert all(len(s.text) <= 1500 for s in segs)


def test_empty_and_whitespace():
    assert segment_content("", ContentType.story) == ([], False)
    assert segment_content("  \n\n  ", ContentType.story) == ([], False)


def test_max_segments_truncates():
    text = "\n\n".join(f"Paragraph number {i} has enough text to stand alone, honestly." for i in range(10))
    segs, truncated = segment_content(text, ContentType.story, max_segments=4)
    assert len(segs) == 4
    assert truncated


def test_single_newline_paragraphs():
    text = "\n".join(f"Line {i} is a standalone paragraph with enough words in it." for i in range(5))
    segs, _ = segment_content(text, ContentType.story)
    _assert_exact(text, segs)
    assert len(segs) == 5
