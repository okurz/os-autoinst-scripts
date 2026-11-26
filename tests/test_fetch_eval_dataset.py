# Copyright SUSE LLC
"""Unit tests for fetch_eval_dataset."""

from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from collections import Counter
from typing import TYPE_CHECKING, Any
from unittest import mock

from scripts.benchmarking import fetch_eval_dataset as fetch
from scripts.benchmarking.fetch_eval_dataset import (
    CLASS_INFRA,
    CLASS_PRODUCT,
    CLASS_TEST,
    InventoryReport,
    Selection,
    build_corpus_rows,
    build_dataset,
    build_inventory,
    classify_bugref,
    extract_ground_truth,
    format_inventory,
    in_window,
    parse_llm_comment,
    row_references,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

LLM_CLASS = "Classification: Product bug\nRestart: NO"


class TestFetchEvalDataset(unittest.TestCase):
    """Parses the LLM comment and derives the ground truth of a job."""

    def test_parse_llm_comment(self) -> None:
        cases = [
            {
                "desc": "Standard bold format with Product bug and restart NO",
                "text": ("**LLM Investigation summary:**\n\nClassification: Product bug\nRestart: NO\nBISECT: NO"),
                "expected_class": CLASS_PRODUCT,
                "expected_restart": "NO",
            },
            {
                "desc": "Backtick and asterisk formatted with Test issue and restart YES",
                "text": ("*Classification*: `Test issue`\n*Restart*: `YES`\n"),
                "expected_class": CLASS_TEST,
                "expected_restart": "YES",
            },
            {
                "desc": "Infrastructure problem without restart",
                "text": ("Some preamble\nClassification: Infrastructure problem\nMore explanation..."),
                "expected_class": CLASS_INFRA,
                "expected_restart": None,
            },
            {
                "desc": "Malformed or human comment without classification",
                "text": "This is just a regular human comment without any LLM header.",
                "expected_class": None,
                "expected_restart": None,
            },
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                res = parse_llm_comment(case["text"])
                if case["expected_class"] is None:
                    assert res is None
                else:
                    assert res is not None
                    assert res.classification == case["expected_class"]
                    assert res.restart == case["expected_restart"]

    def test_classify_bugref(self) -> None:
        cases = [
            {
                "desc": "Bugzilla bsc reference",
                "ref": "bsc#1290026",
                "expected": CLASS_PRODUCT,
            },
            {
                "desc": "Bugzilla boo reference",
                "ref": "boo#1288617",
                "expected": CLASS_PRODUCT,
            },
            {
                "desc": "Bugzilla full url",
                "ref": "https://bugzilla.suse.com/show_bug.cgi?id=123",
                "expected": CLASS_PRODUCT,
            },
            {"desc": "Progress ticket", "ref": "poo#199181", "expected": CLASS_TEST},
            {"desc": "Unknown reference format", "ref": "foo#12345", "expected": None},
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                assert classify_bugref(case["ref"]) == case["expected"]

    def test_extract_ground_truth_from_bugs_metadata(self) -> None:
        cases = [
            {
                "desc": "Job with bsc bug in comment_data",
                "job": {
                    "comment_data": {
                        "bugs": [
                            {
                                "content": "bsc#1290026",
                                "url": "https://bugzilla.suse.com/1290026",
                            }
                        ]
                    }
                },
                "comments": [],
                "expected_class": CLASS_PRODUCT,
                "expected_source": "comment_data.bugs",
            },
            {
                "desc": "Job with poo ticket in comment_data",
                "job": {
                    "comment_data": {
                        "bugs": [
                            {
                                "content": "poo#209976",
                                "url": "https://progress.opensuse.org/209976",
                            }
                        ]
                    }
                },
                "comments": [],
                "expected_class": CLASS_TEST,
                "expected_source": "comment_data.bugs",
            },
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                gt = extract_ground_truth(case["job"], case["comments"])
                assert gt is not None
                assert gt.ground_truth_class == case["expected_class"]
                assert gt.source == case["expected_source"]

    def test_extract_ground_truth_from_human_comments(self) -> None:
        cases = [
            {
                "desc": "Human reviewer referenced a Bugzilla bug in follow-up comment",
                "job": {"comment_data": {"bugs": []}},
                "comments": [
                    {
                        "userName": "geekotest",
                        "text": "**LLM Investigation summary:**\nClassification: Test issue",
                    },
                    {
                        "userName": "alice",
                        "text": "Confirmed product defect, filed bsc#1234567 for this regression.",
                    },
                ],
                "expected_class": CLASS_PRODUCT,
                "expected_ref": "bsc#1234567",
            },
            {
                "desc": "Human reviewer noted infrastructure failure in comment",
                "job": {"comment_data": {"bugs": []}},
                "comments": [
                    {
                        "userName": "geekotest",
                        "text": "**LLM Investigation summary:**\nClassification: Product bug",
                    },
                    {
                        "userName": "bob",
                        "text": "Worker network died, this is clearly an infrastructure failure.",
                    },
                ],
                "expected_class": CLASS_INFRA,
                "expected_ref": "Worker network died, this is clearly an infrastructure failure.",
            },
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                gt = extract_ground_truth(case["job"], case["comments"])
                assert gt is not None
                assert gt.ground_truth_class == case["expected_class"]
                assert gt.reference == case["expected_ref"]


if __name__ == "__main__":
    unittest.main()


def window_job(job_id: int, finished: str | None, refs: tuple[str, ...] = (), comments: int = 0) -> dict[str, Any]:
    """Build a list_ajax job row as the corpus queries see it."""
    return {
        "id": job_id,
        "finished": finished,
        "result": "failed",
        "test": f"test_{job_id}",
        "group": 1,
        "comment_data": {"bugs": [{"content": ref} for ref in refs], "comments": comments},
    }


class TestCorpusSelection(unittest.TestCase):
    """The window, the per-ticket cap and the inventory follow the corpus queries."""

    def test_in_window(self) -> None:
        cases = [
            {
                "desc": "no window keeps a job without a finished date",
                "job": window_job(1, None),
                "since": None,
                "until": None,
                "expected": True,
            },
            {
                "desc": "job on the since bound is kept",
                "job": window_job(2, "2026-05-01T00:00:00Z"),
                "since": dt.date(2026, 5, 1),
                "until": None,
                "expected": True,
            },
            {
                "desc": "job before since is dropped",
                "job": window_job(3, "2026-04-30T23:59:59Z"),
                "since": dt.date(2026, 5, 1),
                "until": None,
                "expected": False,
            },
            {
                "desc": "job after until is dropped",
                "job": window_job(4, "2026-11-02T00:00:00Z"),
                "since": None,
                "until": dt.date(2026, 11, 1),
                "expected": False,
            },
            {
                "desc": "window drops a job without a finished date",
                "job": window_job(5, None),
                "since": dt.date(2026, 5, 1),
                "until": None,
                "expected": False,
            },
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                assert in_window(case["job"], case["since"], case["until"]) == case["expected"]

    def test_row_references(self) -> None:
        cases = [
            {
                "desc": "content refs are lowercased",
                "job": window_job(1, "2026-06-01T00:00:00Z", ("boo#1289464",)),
                "expected": ["boo#1289464"],
            },
            {
                "desc": "url is used when content is empty",
                "job": {"comment_data": {"bugs": [{"url": "https://bugzilla.suse.com/1289038"}]}},
                "expected": ["https://bugzilla.suse.com/1289038"],
            },
            {
                "desc": "duplicate refs collapse to one",
                "job": window_job(2, "2026-06-01T00:00:00Z", ("poo#209382", "POO#209382")),
                "expected": ["poo#209382"],
            },
            {"desc": "job without bugs has no reference", "job": window_job(3, "2026-06-01T00:00:00Z"), "expected": []},
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                assert row_references(case["job"]) == case["expected"]

    def test_build_corpus_rows_applies_the_window_and_the_cap(self) -> None:
        jobs = [
            *(window_job(index, "2026-06-01T08:00:00Z", ("boo#1289464",)) for index in range(1, 4)),
            window_job(5, "2026-07-01T08:00:00Z", ("poo#209382", "boo#1246013")),
            window_job(6, "2026-01-01T08:00:00Z", ("boo#1288617",)),
            window_job(7, "2026-07-02T08:00:00Z"),
        ]
        cases = [
            {
                "desc": "window and cap apply, a job keeps its first reference only",
                "selection": Selection(dt.date(2026, 5, 1), dt.date(2026, 8, 1), 2),
                "expected": {"boo#1289464": 2, "poo#209382": 1},
            },
            {
                "desc": "a job whose own ticket is at the cap is skipped even when it names another ticket",
                "jobs": [
                    window_job(1, "2026-06-01T08:00:00Z", ("poo#209382",)),
                    window_job(2, "2026-06-02T08:00:00Z", ("poo#209382",)),
                    window_job(3, "2026-06-03T08:00:00Z", ("poo#209382", "boo#1246013")),
                ],
                "selection": Selection(dt.date(2026, 5, 1), dt.date(2026, 8, 1), 2),
                "expected": {"poo#209382": 2},
            },
            {
                "desc": "without a cap every in-window referenced job stays",
                "selection": Selection(dt.date(2026, 5, 1), dt.date(2026, 8, 1), None),
                "expected": {"boo#1289464": 3, "poo#209382": 1},
            },
        ]
        for case in cases:
            with self.subTest(desc=case["desc"]):
                with mock.patch.object(fetch, "_candidate_jobs", return_value=case.get("jobs", jobs)):
                    rows = build_corpus_rows(selection=case["selection"])
                assert Counter(row.reference for row in rows) == Counter(case["expected"])


def test_build_inventory_counts_months_and_references() -> None:
    jobs = [
        window_job(1, "2026-06-01T08:00:00Z", ("boo#1289464",)),
        window_job(2, "2026-06-02T08:00:00Z", ("boo#1289464", "poo#209382")),
        window_job(3, "2026-07-03T08:00:00Z", ("poo#209382",)),
        window_job(4, "2026-07-04T08:00:00Z"),
        window_job(5, "2026-04-01T08:00:00Z", ("boo#1",)),
    ]
    with mock.patch.object(fetch, "_candidate_jobs", return_value=jobs):
        report = build_inventory(selection=Selection(dt.date(2026, 5, 1), dt.date(2026, 8, 1)))

    assert report.jobs == 4
    assert report.rows_with_reference == 3
    assert report.months == {"2026-06": 2, "2026-07": 2}
    assert report.references == {"boo#1289464": 2, "poo#209382": 2}
    assert (report.earliest, report.latest) == ("2026-06-01", "2026-07-04")


def test_format_inventory() -> None:
    report = InventoryReport(
        jobs=3,
        rows_with_reference=2,
        references={"boo#1289464": 2, "poo#209382": 1},
        months={"2026-06": 2, "2026-07": 1},
        earliest="2026-06-01",
        latest="2026-07-04",
        since=dt.date(2026, 6, 1),
        until=dt.date(2026, 7, 31),
    )

    output = format_inventory(report)

    assert "Inventory: 3 LLM-commented jobs" in output
    assert "2026-06  2" in output
    assert "boo#1289464  2" in output


def test_build_dataset_honours_the_window_and_the_ticket_cap() -> None:
    jobs = [
        *(window_job(index, "2026-06-01T08:00:00Z", ("boo#1289464",)) for index in range(1, 5)),
        window_job(6, "2026-01-01T08:00:00Z", ("boo#1288617",)),
    ]
    with (
        mock.patch.object(fetch, "_candidate_jobs", return_value=jobs),
        mock.patch.object(fetch, "get_json", return_value=[{"userName": "geekotest", "text": LLM_CLASS}]),
        mock.patch.object(fetch, "REQUEST_DELAY", 0),
    ):
        entries = build_dataset(selection=Selection(dt.date(2026, 5, 1), dt.date(2026, 8, 1), 2), min_entries=100)

    assert [entry.job_id for entry in entries] == [1, 2]
    assert {entry.reference for entry in entries} == {"boo#1289464"}


def test_main_inventory_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jobs = [window_job(1, "2026-06-01T08:00:00Z", ("boo#1289464",))]
    output = tmp_path / "eval_dataset.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_eval_dataset.py", "--inventory", "--groups", "1", "--output", str(output)],
    )
    with mock.patch.object(fetch, "_candidate_jobs", return_value=jobs):
        assert fetch.main() == 0

    assert not output.exists()
    assert "Inventory: 1 LLM-commented jobs" in capsys.readouterr().out


def test_main_corpus_output_writes_the_referenced_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    jobs = [
        window_job(1, "2026-06-01T08:00:00Z", ("boo#1289464",)),
        window_job(2, "2026-06-02T08:00:00Z"),
    ]
    output = tmp_path / "corpus.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_eval_dataset.py", "--corpus-output", str(output), "--groups", "1", "--max-per-ticket", "1"],
    )
    with mock.patch.object(fetch, "_candidate_jobs", return_value=jobs):
        assert fetch.main() == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["metadata"]["rows"] == 1
    assert payload["metadata"]["references"] == 1
    assert payload["entries"][0]["reference"] == "boo#1289464"
