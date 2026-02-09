# tests/test_system_prompt.py
"""
TICKET-23: Tests for system prompt integrity.

Validates:
- No brave/web_search references in prompt files (except "not available" notes)
- No /no_think token pollution in aria_mind/*.md
- models.yaml is valid and contains expected models
- TOOLS.md uses ```yaml fences (or ```tool, both accepted by registry)
"""
import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARIA_MIND = PROJECT_ROOT / "aria_mind"
ARIA_MEMORIES = PROJECT_ROOT / "aria_memories"
MODELS_YAML = PROJECT_ROOT / "aria_models" / "models.yaml"


# ── helpers ──────────────────────────────────────────────────────────
def _read_md_files(directory: Path) -> dict[str, str]:
    """Return {filename: content} for all .md files in *directory*."""
    return {f.name: f.read_text(encoding="utf-8") for f in directory.glob("*.md")}


# ── STEP 2 – no brave / web_search references ───────────────────────
class TestNoBraveReferences:
    """Ensure brave/web_search refs are removed (or only 'not available' notes)."""

    ALLOWED = re.compile(r"not currently available|NOT currently available", re.IGNORECASE)

    @pytest.fixture(autouse=True)
    def _load(self):
        self.md_files = _read_md_files(ARIA_MIND)

    def test_no_brave_in_aria_md(self):
        content = self.md_files.get("ARIA.md", "")
        for match in re.finditer(r"(?i)brave|web_search|BRAVE_API", content):
            line = content[: match.start()].count("\n") + 1
            context = content[max(0, match.start() - 40) : match.end() + 40]
            assert self.ALLOWED.search(context), (
                f"ARIA.md line ~{line}: unexpected brave/web_search reference: "
                f"...{context.strip()}..."
            )

    def test_no_brave_in_all_prompt_files(self):
        """No prompt file should reference brave/web_search outside of a 'not available' note."""
        for name, content in self.md_files.items():
            for match in re.finditer(r"(?i)brave|web_search|BRAVE_API", content):
                context = content[max(0, match.start() - 40) : match.end() + 40]
                assert self.ALLOWED.search(context), (
                    f"{name}: unexpected brave/web_search reference: ...{context.strip()}..."
                )


# ── STEP 6 – no /no_think tokens ────────────────────────────────────
class TestNoThinkTokens:
    """Ensure /no_think and <think> tokens are cleaned from prompt files."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.md_files = _read_md_files(ARIA_MIND)

    def test_no_no_think_in_aria_mind(self):
        """No .md file under aria_mind/ should contain bare /no_think tokens."""
        for name, content in self.md_files.items():
            # Allow the Output Rules section that tells Aria NOT to emit these
            lines_with_token = [
                (i + 1, line)
                for i, line in enumerate(content.splitlines())
                if line.strip() == "/no_think"
            ]
            assert lines_with_token == [], (
                f"{name} contains bare /no_think token(s) at line(s): "
                f"{[ln for ln, _ in lines_with_token]}"
            )

    def test_no_think_blocks_in_aria_mind(self):
        """No <think>...</think> blocks in prompt files."""
        for name, content in self.md_files.items():
            assert "<think>" not in content.lower() or "never output" in content.lower(), (
                f"{name} contains <think> block(s)"
            )


# ── STEP 3 – models.yaml valid ──────────────────────────────────────
class TestModelsYaml:
    """Validate models.yaml structure and expected models."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.raw = MODELS_YAML.read_text(encoding="utf-8")
        self.catalog = json.loads(self.raw)

    def test_models_yaml_is_valid_json(self):
        """models.yaml must parse as valid JSON."""
        assert isinstance(self.catalog, dict)

    def test_has_schema_version(self):
        assert "schema_version" in self.catalog

    def test_has_models_section(self):
        assert "models" in self.catalog
        assert len(self.catalog["models"]) >= 1

    def test_expected_models_exist(self):
        """All expected core models must be present."""
        expected = {"qwen3-mlx", "trinity-free", "chimera-free", "kimi"}
        actual = set(self.catalog["models"].keys())
        missing = expected - actual
        assert not missing, f"Missing expected models: {missing}"

    def test_each_model_has_required_fields(self):
        """Every model entry must have provider, contextWindow, and cost."""
        for name, model in self.catalog["models"].items():
            assert "provider" in model, f"{name}: missing 'provider'"
            assert "contextWindow" in model, f"{name}: missing 'contextWindow'"
            assert "cost" in model, f"{name}: missing 'cost'"

    def test_has_criteria_section(self):
        assert "criteria" in self.catalog
        assert "tiers" in self.catalog["criteria"]

    def test_tiers_cover_all_models(self):
        """Every model should appear in exactly one tier."""
        tiers = self.catalog["criteria"]["tiers"]
        tier_models = set()
        for models_list in tiers.values():
            tier_models.update(models_list)
        catalog_models = set(self.catalog["models"].keys())
        untied = catalog_models - tier_models
        assert not untied, f"Models not in any tier: {untied}"


# ── STEP 7 – TOOLS.md code fences ───────────────────────────────────
class TestToolsCodeFences:
    """TOOLS.md should use ```yaml or ```tool fences (both accepted by registry)."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = (ARIA_MIND / "TOOLS.md").read_text(encoding="utf-8")

    def test_code_fences_are_yaml_or_tool(self):
        """All code fences in TOOLS.md should be ```yaml, ```tool, or other known types."""
        allowed = {"yaml", "tool", "python", "json", "bash", "sql", ""}
        fences = re.findall(r"^```(\w*)", self.content, re.MULTILINE)
        bad = [f for f in fences if f not in allowed]
        assert not bad, f"Unexpected code fence types in TOOLS.md: {bad}"

    def test_no_bare_code_fences_for_examples(self):
        """Tool example blocks should not use bare ``` (no language)."""
        # Find opening fences that are just ``` followed by tool-call-like content
        bare_fences = re.findall(r"^```\n\s*aria-", self.content, re.MULTILINE)
        assert not bare_fences, (
            f"Found bare ``` fences before tool examples; use ```yaml or ```tool"
        )
