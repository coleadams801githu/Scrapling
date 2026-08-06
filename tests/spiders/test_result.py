"""Tests for the result module (ItemList, CrawlStats, CrawlResult)."""

import json
import tempfile
from pathlib import Path

import pytest

from scrapling.spiders.result import ItemList, CrawlStats, CrawlResult


class TestItemList:
    """Test ItemList functionality."""

    def test_itemlist_is_list(self):
        """Test that ItemList is a list subclass."""
        items = ItemList()

        assert isinstance(items, list)

    def test_itemlist_basic_operations(self):
        """Test basic list operations work."""
        items = ItemList()

        items.append({"id": 1})
        items.append({"id": 2})

        assert len(items) == 2
        assert items[0] == {"id": 1}

    def test_to_json_creates_file(self):
        """Test to_json creates JSON file."""
        items = ItemList()
        items.append({"name": "test", "value": 123})
        items.append({"name": "test2", "value": 456})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            items.to_json(path)

            assert path.exists()

            content = json.loads(path.read_text())
            assert len(content) == 2
            assert content[0]["name"] == "test"

    def test_to_json_creates_parent_directory(self):
        """Test to_json creates parent directories."""
        items = ItemList()
        items.append({"data": "test"})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dirs" / "output.json"
            items.to_json(path)

            assert path.exists()

    def test_to_json_with_indent(self):
        """Test to_json with indentation."""
        items = ItemList()
        items.append({"key": "value"})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            items.to_json(path, indent=True)

            content = path.read_text()
            # Indented JSON should have newlines
            assert "\n" in content

    def test_to_jsonl_creates_file(self):
        """Test to_jsonl creates JSON Lines file."""
        items = ItemList()
        items.append({"id": 1, "name": "first"})
        items.append({"id": 2, "name": "second"})
        items.append({"id": 3, "name": "third"})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.jsonl"
            items.to_jsonl(path)

            assert path.exists()

            lines = path.read_text().strip().split("\n")
            assert len(lines) == 3

            # Each line should be valid JSON
            for line in lines:
                parsed = json.loads(line)
                assert "id" in parsed
                assert "name" in parsed

    def test_to_jsonl_one_object_per_line(self):
        """Test that JSONL has one JSON object per line."""
        items = ItemList()
        items.append({"line": 1})
        items.append({"line": 2})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.jsonl"
            items.to_jsonl(path)

            lines = path.read_text().strip().split("\n")

            assert json.loads(lines[0])["line"] == 1
            assert json.loads(lines[1])["line"] == 2

    def test_to_csv_creates_file(self):
        """Test to_csv creates a CSV file with headers."""
        items = ItemList()
        items.append({"name": "Alice", "age": 30})
        items.append({"name": "Bob", "age": 25})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            items.to_csv(path)

            assert path.exists()
            lines = path.read_text().splitlines()
            assert lines[0] == "name,age"
            assert "Alice" in lines[1]
            assert "Bob" in lines[2]

    def test_to_csv_custom_fieldnames(self):
        """Test to_csv respects explicit fieldnames order."""
        items = ItemList()
        items.append({"a": 1, "b": 2, "c": 3})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            items.to_csv(path, fieldnames=["c", "a", "b"])

            header = path.read_text().splitlines()[0]
            assert header == "c,a,b"

    def test_to_csv_custom_delimiter(self):
        """Test to_csv respects custom delimiter."""
        items = ItemList()
        items.append({"x": 1, "y": 2})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            items.to_csv(path, delimiter=";")

            header = path.read_text().splitlines()[0]
            assert ";" in header

    def test_to_csv_empty_list_no_file_written(self):
        """Test to_csv with empty list emits a warning and writes no data."""
        items = ItemList()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            items.to_csv(path)
            # File should not be created for empty list
            assert not path.exists()

    def test_to_csv_creates_parent_directory(self):
        """Test to_csv creates parent directories."""
        items = ItemList()
        items.append({"k": "v"})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "output.csv"
            items.to_csv(path)
            assert path.exists()


class TestCrawlStats:
    """Test CrawlStats dataclass."""

    def test_default_values(self):
        """Test CrawlStats default values."""
        stats = CrawlStats()

        assert stats.requests_count == 0
        assert stats.concurrent_requests == 0
        assert stats.failed_requests_count == 0
        assert stats.response_bytes == 0
        assert stats.items_scraped == 0
        assert stats.items_dropped == 0
        assert stats.start_time == 0.0
        assert stats.end_time == 0.0
        assert stats.custom_stats == {}
        assert stats.response_status_count == {}
        assert stats.proxies == []

    def test_elapsed_seconds(self):
        """Test elapsed_seconds property."""
        stats = CrawlStats(start_time=100.0, end_time=150.0)

        assert stats.elapsed_seconds == 50.0

    def test_requests_per_second(self):
        """Test requests_per_second calculation."""
        stats = CrawlStats(
            requests_count=100,
            start_time=0.0,
            end_time=10.0,
        )

        assert stats.requests_per_second == 10.0

    def test_requests_per_second_zero_elapsed(self):
        """Test requests_per_second when elapsed is zero."""
        stats = CrawlStats(
            requests_count=100,
            start_time=0.0,
            end_time=0.0,
        )

        assert stats.requests_per_second == 0.0

    def test_increment_status(self):
        """Test increment_status method."""
        stats = CrawlStats()

        stats.increment_status(200)
        stats.increment_status(200)
        stats.increment_status(404)

        assert stats.response_status_count == {"status_200": 2, "status_404": 1}

    def test_increment_response_bytes(self):
        """Test increment_response_bytes method."""
        stats = CrawlStats()

        stats.increment_response_bytes("example.com", 1000)
        stats.increment_response_bytes("example.com", 500)
        stats.increment_response_bytes("other.com", 2000)

        assert stats.response_bytes == 3500
        assert stats.domains_response_bytes == {
            "example.com": 1500,
            "other.com": 2000,
        }

    def test_increment_requests_count(self):
        """Test increment_requests_count method."""
        stats = CrawlStats()

        stats.increment_requests_count("session1")
        stats.increment_requests_count("session1")
        stats.increment_requests_count("session2")

        assert stats.requests_count == 3
        assert stats.sessions_requests_count == {"session1": 2, "session2": 1}

    def test_to_dict(self):
        """Test to_dict method returns all stats."""
        stats = CrawlStats(
            items_scraped=10,
            items_dropped=2,
            requests_count=15,
            start_time=0.0,
            end_time=5.0,
        )
        stats.increment_status(200)

        result = stats.to_dict()

        assert result["items_scraped"] == 10
        assert result["items_dropped"] == 2
        assert result["requests_count"] == 15
        assert result["elapsed_seconds"] == 5.0
        assert result["requests_per_second"] == 3.0
        assert result["response_status_count"] == {"status_200": 1}

    def test_custom_stats(self):
        """Test custom_stats can be used."""
        stats = CrawlStats()
        stats.custom_stats["my_metric"] = 42
        stats.custom_stats["another"] = "value"

        assert stats.custom_stats["my_metric"] == 42
        assert stats.to_dict()["custom_stats"]["my_metric"] == 42

    def test_to_json_creates_file(self):
        """Test CrawlStats.to_json() writes a valid JSON file."""
        stats = CrawlStats(items_scraped=7, requests_count=10, start_time=0.0, end_time=2.0)
        stats.increment_status(200)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stats.json"
            stats.to_json(path)

            assert path.exists()
            data = json.loads(path.read_text())
            assert data["items_scraped"] == 7
            assert data["requests_count"] == 10

    def test_to_json_with_indent(self):
        """Test CrawlStats.to_json() pretty-prints when indent=True."""
        stats = CrawlStats()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stats.json"
            stats.to_json(path, indent=True)
            content = path.read_text()
            assert "\n" in content


class TestCrawlResult:
    """Test CrawlResult dataclass."""

    def test_basic_creation(self):
        """Test basic CrawlResult creation."""
        stats = CrawlStats(items_scraped=5)
        items = ItemList()
        items.extend([{"id": i} for i in range(5)])

        result = CrawlResult(stats=stats, items=items)

        assert result.stats.items_scraped == 5
        assert len(result.items) == 5
        assert result.paused is False

    def test_completed_property_true_when_not_paused(self):
        """Test completed is True when not paused."""
        result = CrawlResult(
            stats=CrawlStats(),
            items=ItemList(),
            paused=False,
        )

        assert result.completed is True

    def test_completed_property_false_when_paused(self):
        """Test completed is False when paused."""
        result = CrawlResult(
            stats=CrawlStats(),
            items=ItemList(),
            paused=True,
        )

        assert result.completed is False

    def test_len_returns_item_count(self):
        """Test len returns number of items."""
        items = ItemList()
        items.extend([{"id": i} for i in range(10)])

        result = CrawlResult(stats=CrawlStats(), items=items)

        assert len(result) == 10

    def test_iter_yields_items(self):
        """Test iteration yields items."""
        items = ItemList()
        items.extend([{"id": 1}, {"id": 2}, {"id": 3}])

        result = CrawlResult(stats=CrawlStats(), items=items)

        collected = list(result)

        assert collected == [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_result_with_stats(self):
        """Test CrawlResult with populated stats."""
        stats = CrawlStats(
            requests_count=100,
            items_scraped=50,
            failed_requests_count=5,
            start_time=0.0,
            end_time=10.0,
        )
        items = ItemList()

        result = CrawlResult(stats=stats, items=items)

        assert result.stats.requests_count == 100
        assert result.stats.items_scraped == 50
        assert result.stats.requests_per_second == 10.0

    def test_save_report_creates_json(self):
        """Test CrawlResult.save_report() writes a JSON report."""
        stats = CrawlStats(items_scraped=3, requests_count=5, start_time=0.0, end_time=1.0)
        items = ItemList([{"id": i} for i in range(3)])
        result = CrawlResult(stats=stats, items=items)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            result.save_report(path)

            assert path.exists()
            data = json.loads(path.read_text())
            assert data["items_count"] == 3
            assert data["items_scraped"] == 3
            assert data["paused"] is False

    def test_save_report_paused_flag(self):
        """Test CrawlResult.save_report() records paused state correctly."""
        result = CrawlResult(stats=CrawlStats(), items=ItemList(), paused=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            result.save_report(path)
            data = json.loads(path.read_text())
            assert data["paused"] is True

    def test_save_report_creates_parent_dirs(self):
        """Test CrawlResult.save_report() creates parent directories."""
        result = CrawlResult(stats=CrawlStats(), items=ItemList())

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reports" / "crawl.json"
            result.save_report(path)
            assert path.exists()


class TestCrawlResultIntegration:
    """Integration tests for result classes."""

    def test_full_workflow(self):
        """Test realistic workflow with all result classes."""
        # Simulate a crawl
        stats = CrawlStats(start_time=1000.0)

        # Simulate requests
        for _ in range(10):
            stats.increment_requests_count("default")
            stats.increment_status(200)
            stats.increment_response_bytes("example.com", 5000)

        # Simulate some failures
        stats.failed_requests_count = 2
        stats.blocked_requests_count = 1

        # Collect items
        items = ItemList()
        for i in range(8):
            items.append({"product_id": i, "name": f"Product {i}"})
            stats.items_scraped += 1

        # Finish crawl
        stats.end_time = 1005.0

        # Create result
        result = CrawlResult(stats=stats, items=items, paused=False)

        # Verify
        assert result.completed is True
        assert len(result) == 8
        assert result.stats.requests_count == 10
        assert result.stats.requests_per_second == 2.0
        assert result.stats.response_bytes == 50000
