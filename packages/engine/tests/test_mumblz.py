"""Mumblz title agent tests."""

from tokenish_engine.agents import mumblz_name_thread, mumblz_title


def test_mumblz_keeps_vowels_two_words():
    assert mumblz_title("Neon Cityscape Review") == "Neon Cityscape"
    assert mumblz_title("Combinatorics Critique Audit") == "Combinatorics Critique"
    assert mumblz_title("") == "Fresh Thread"


def test_mumblz_two_words_combinatorics_chat():
    msgs = [
        {
            "role": "user",
            "content": (
                "Deeply Assess the attached. Then check its validity with trusted online "
                "sources. Then generate a one page exec summary. Then act as adversarial "
                "peer reviewer. Unicombinatorics freefactorial G-Triangle."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "The Freefactorial framework and Unicombinatorics claims overlap known "
                "partial permutation sums. Peer review finds nomenclature inflation."
            ),
        },
    ]
    title = mumblz_name_thread(msgs)
    parts = title.split()
    assert len(parts) == 2
    # Vowels kept — readable English words
    assert any(c in title.lower() for c in "aeiou")
    joined = title.lower()
    assert "combinatorics" in joined or "critique" in joined or "digest" in joined


def test_mumblz_two_words_palette_chat():
    msgs = [
        {"role": "user", "content": "Deeply Assess the attached. I want color and details of ratios and styles."},
        {
            "role": "assistant",
            "content": "Neon parking booth night cityscape with painterly blues and warm accents.",
        },
    ]
    title = mumblz_name_thread(msgs)
    parts = title.split()
    assert len(parts) == 2
    assert any(c in title.lower() for c in "aeiou")
