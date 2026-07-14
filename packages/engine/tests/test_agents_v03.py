"""Rainman/Agatha seal smoke tests — factual only."""

from tokenish_engine.agents import archive_rainman_brief, interrogate_run, intake_local_savings
from tokenish_engine.agents.neoborg import cross_vet_and_record
from tokenish_engine.pipeline import optimize


def test_rainman_no_llm_and_counts_stages():
    brief = interrogate_run(
        stages=["ingest", "lcs", "dedupe_drop_2", "split_exec", "its_disabled_consent"],
        tokex={"total_tokex": 1000, "tokex_this_run": 800, "saved_tokex": 200, "saved_pct": 20.0},
        fidelity_mode="loyalty",
    )
    assert brief["agent"] == "Rainman"
    assert brief["llm_used"] is False
    assert brief["tokex"]["saved_tokex"] == 200
    fired = [c["cylinder"] for c in brief["cylinders"] if c["fired"]]
    assert "ingest" in fired
    assert "dedupe" in fired
    assert "its_skipped_fidelity" in fired or "its_disabled_consent" in str(brief["stages"])


def test_agatha_archives_and_hive_chain():
    brief = interrogate_run(
        stages=["ingest", "lcs", "prompt_only"],
        tokex={"total_tokex": 40, "tokex_this_run": 38, "saved_tokex": 2, "saved_pct": 5.0},
    )
    receipt = archive_rainman_brief(brief)
    assert receipt["archived"] is True
    brown = intake_local_savings({"tokex": brief["tokex"], "rainman": brief, "cylinders": brief["cylinders"]})
    assert brown["accepted"] is True
    neo = cross_vet_and_record(brown["handoff"])
    assert neo["accepted"] is True
    assert neo["broadcast"] is False


def test_optimize_seals_rainman():
    result = optimize(prompt="hello there friend how are you today doing fine?", files=None)
    assert result.rainman.get("agent") == "Rainman"
    assert result.agatha.get("archived") is True
    assert result.fidelity_mode in {"loyalty", "savings_consent"}
