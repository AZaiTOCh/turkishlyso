"""tokenish agents — Mumblz, Rainman, Agatha, Mrs. Brown, NeoBorg."""

from tokenish_engine.agents.agatha import archive_rainman_brief, cylinder_rollups, recent_runs
from tokenish_engine.agents.mrs_brown import intake_local_savings
from tokenish_engine.agents.mumblz import (
    interpret_thread_title,
    interpret_thread_title_llm,
    mumblz_name_thread,
    mumblz_name_thread_llm,
    mumblz_title,
    normalize_three_word_title,
    normalize_two_word_title,
    strip_vowels_word,
)
from tokenish_engine.agents.neoborg import clock_snapshot, cross_vet_and_record
from tokenish_engine.agents.rainman import interrogate_run

__all__ = [
    "mumblz_name_thread",
    "mumblz_name_thread_llm",
    "mumblz_title",
    "strip_vowels_word",
    "normalize_three_word_title",
    "normalize_two_word_title",
    "interpret_thread_title",
    "interpret_thread_title_llm",
    "interrogate_run",
    "archive_rainman_brief",
    "cylinder_rollups",
    "recent_runs",
    "intake_local_savings",
    "cross_vet_and_record",
    "clock_snapshot",
]
