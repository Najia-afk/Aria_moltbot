"""Tests for aria_mind/cron_jobs.yaml configuration."""

import pathlib

import yaml
import pytest

pytestmark = pytest.mark.unit

CRON_YAML = pathlib.Path(__file__).resolve().parent.parent / "aria_mind" / "cron_jobs.yaml"

REQUIRED_FIELDS = {"agent", "session", "text"}


@pytest.fixture(scope="module")
def cron_data():
    """Load and parse cron_jobs.yaml."""
    with open(CRON_YAML) as f:
        data = yaml.safe_load(f)
    return data


@pytest.fixture(scope="module")
def jobs(cron_data):
    """Return the list of job dicts keyed by name."""
    return {job["name"]: job for job in cron_data["jobs"]}


# ── Valid YAML ────────────────────────────────────────────────────


class TestCronYAMLValidity:
    def test_yaml_is_valid(self):
        """cron_jobs.yaml must be parseable YAML."""
        with open(CRON_YAML) as f:
            data = yaml.safe_load(f)
        assert data is not None, "YAML parsed to None"

    def test_has_jobs_key(self, cron_data):
        assert "jobs" in cron_data, "Top-level 'jobs' key missing"

    def test_jobs_is_list(self, cron_data):
        assert isinstance(cron_data["jobs"], list), "'jobs' must be a list"

    def test_all_jobs_have_name(self, cron_data):
        for i, job in enumerate(cron_data["jobs"]):
            assert "name" in job, f"Job index {i} missing 'name'"


# ── Required fields ───────────────────────────────────────────────


class TestRequiredFields:
    def test_all_jobs_have_required_fields(self, jobs):
        for name, job in jobs.items():
            for field in REQUIRED_FIELDS:
                assert field in job, f"Job '{name}' missing required field '{field}'"

    def test_all_jobs_have_schedule(self, jobs):
        for name, job in jobs.items():
            has_schedule = "cron" in job or "every" in job
            assert has_schedule, f"Job '{name}' has neither 'cron' nor 'every'"


# ── Specific job checks ──────────────────────────────────────────


class TestSocialPost:
    def test_exists(self, jobs):
        assert "social_post" in jobs

    def test_fires_at_6h_intervals(self, jobs):
        job = jobs["social_post"]
        assert "cron" in job, "social_post should use 'cron' not 'every'"
        assert job["cron"] == "0 0 0,6,12,18 * * *", (
            f"Expected 6-hour cron schedule, got: {job['cron']}"
        )


class TestWorkCycle:
    def test_exists(self, jobs):
        assert "work_cycle" in jobs

    def test_is_15_min(self, jobs):
        job = jobs["work_cycle"]
        assert "every" in job, "work_cycle should use 'every'"
        assert job["every"] == "15m", f"Expected '15m', got: {job['every']}"


class TestMemoryConsolidation:
    def test_exists(self, jobs):
        assert "memory_consolidation" in jobs

    def test_weekly_sunday(self, jobs):
        job = jobs["memory_consolidation"]
        assert "cron" in job
        assert job["cron"] == "0 0 5 * * 0", (
            f"Expected weekly Sunday 5 AM UTC, got: {job['cron']}"
        )

    def test_has_required_fields(self, jobs):
        job = jobs["memory_consolidation"]
        for field in REQUIRED_FIELDS:
            assert field in job, f"memory_consolidation missing '{field}'"

    def test_delivery_is_chat(self, jobs):
        job = jobs["memory_consolidation"]
        assert job.get("delivery") == "chat"


class TestSixHourReview:
    def test_exists(self, jobs):
        assert "six_hour_review" in jobs

    def test_specifies_tool_capable_model(self, jobs):
        job = jobs["six_hour_review"]
        text = job["text"].lower()
        assert "trinity-free" in text or "qwen3-next-free" in text, (
            "six_hour_review should specify a tool-capable model in its text"
        )
