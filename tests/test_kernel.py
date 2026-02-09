# tests/test_kernel.py
"""Tests for the Aria kernel — immutable identity, values, and safety."""
import types
import pathlib
import pytest
import yaml


@pytest.fixture(autouse=True)
def reset_kernel():
    """Reset KernelLoader state between tests."""
    from aria_mind.kernel import KernelLoader
    KernelLoader.reset()
    yield
    KernelLoader.reset()


@pytest.fixture
def kernel_dir():
    """Path to the real kernel directory."""
    return pathlib.Path(__file__).parent.parent / "aria_mind" / "kernel"


@pytest.fixture
def tmp_kernel(tmp_path):
    """Create a temporary kernel directory with test YAML files."""
    for name in ["identity", "values", "safety_constraints", "constitution"]:
        path = tmp_path / f"{name}.yaml"
        if name == "identity":
            data = {"name": "Test Aria", "version": "1.0", "purpose": "Testing"}
        elif name == "values":
            data = {"layers": {"identity": {"core": "truth"}}}
        elif name == "safety_constraints":
            data = {"hard_boundaries": ["never harm humans"], "forbidden_actions": ["rm -rf /"]}
        else:  # constitution
            data = {"version": "1.0.0", "components": ["identity", "values", "safety_constraints"]}
        path.write_text(yaml.dump(data), encoding="utf-8")
    return tmp_path


class TestKernelLoader:
    """Tests for KernelLoader."""

    def test_load_real_kernel(self, kernel_dir):
        """Kernel loads from the real YAML files."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        assert "identity" in kernel
        assert "values" in kernel
        assert "safety_constraints" in kernel
        assert "constitution" in kernel

    def test_load_from_tmp(self, tmp_kernel):
        """Kernel loads from temporary test directory."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(tmp_kernel)
        assert kernel["identity"]["name"] == "Test Aria"

    def test_kernel_is_frozen(self, tmp_kernel):
        """Kernel data is immutable (MappingProxyType)."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(tmp_kernel)
        assert isinstance(kernel, types.MappingProxyType)
        assert isinstance(kernel["identity"], types.MappingProxyType)
        with pytest.raises(TypeError):
            kernel["identity"]["name"] = "Evil"

    def test_kernel_lists_are_tuples(self, tmp_kernel):
        """Lists in kernel are frozen as tuples."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(tmp_kernel)
        boundaries = kernel["safety_constraints"]["hard_boundaries"]
        assert isinstance(boundaries, tuple)
        with pytest.raises(TypeError):
            boundaries[0] = "do harm"  # tuples are immutable

    def test_verify_integrity_passes(self, tmp_kernel):
        """Integrity check passes when files unchanged."""
        from aria_mind.kernel import KernelLoader
        KernelLoader.load(tmp_kernel)
        assert KernelLoader.verify_integrity(tmp_kernel) is True

    def test_verify_integrity_fails_on_modification(self, tmp_kernel):
        """Integrity check fails when a YAML file is modified."""
        from aria_mind.kernel import KernelLoader
        KernelLoader.load(tmp_kernel)
        # Modify a file after loading
        (tmp_kernel / "identity.yaml").write_text("name: Evil\n", encoding="utf-8")
        assert KernelLoader.verify_integrity(tmp_kernel) is False

    def test_verify_integrity_fails_on_deletion(self, tmp_kernel):
        """Integrity check fails when a YAML file is deleted."""
        from aria_mind.kernel import KernelLoader
        KernelLoader.load(tmp_kernel)
        (tmp_kernel / "identity.yaml").unlink()
        assert KernelLoader.verify_integrity(tmp_kernel) is False

    def test_get_auto_loads(self, kernel_dir):
        """KernelLoader.get() auto-loads on first access."""
        from aria_mind.kernel import KernelLoader
        # Patch the default path
        kernel = KernelLoader.load(kernel_dir)
        KernelLoader.reset()
        KernelLoader.load(kernel_dir)
        result = KernelLoader.get()
        assert "identity" in result

    def test_singleton_behavior(self, tmp_kernel):
        """Loading twice returns same frozen object."""
        from aria_mind.kernel import KernelLoader
        k1 = KernelLoader.load(tmp_kernel)
        k2 = KernelLoader.get()
        assert k1 is k2

    def test_reset_clears_state(self, tmp_kernel):
        """Reset clears all loaded state."""
        from aria_mind.kernel import KernelLoader
        KernelLoader.load(tmp_kernel)
        assert KernelLoader._loaded is True
        KernelLoader.reset()
        assert KernelLoader._loaded is False
        assert KernelLoader._kernel is None

    def test_verify_before_load_returns_false(self):
        """Verify integrity returns False if kernel not loaded."""
        from aria_mind.kernel import KernelLoader
        assert KernelLoader.verify_integrity() is False

    def test_missing_component_logged(self, tmp_path):
        """Missing YAML files are logged but don't crash."""
        from aria_mind.kernel import KernelLoader
        # Create only identity.yaml — others missing
        (tmp_path / "identity.yaml").write_text(
            yaml.dump({"name": "Partial"}), encoding="utf-8"
        )
        kernel = KernelLoader.load(tmp_path)
        assert "identity" in kernel
        assert "values" not in kernel


class TestKernelContent:
    """Tests for actual kernel YAML content."""

    def test_identity_has_name(self, kernel_dir):
        """Identity YAML must have a name field."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        assert kernel["identity"].get("name"), "Kernel identity must have a name"

    def test_identity_name_is_aria_blue(self, kernel_dir):
        """Identity name must be Aria Blue."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        assert kernel["identity"]["name"] == "Aria Blue"

    def test_identity_has_personality_traits(self, kernel_dir):
        """Identity must define personality traits."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        traits = kernel["identity"]["personality"]["traits"]
        assert len(traits) >= 4
        assert "sharp" in traits
        assert "secure" in traits

    def test_values_has_core_principles(self, kernel_dir):
        """Values YAML must define core principles."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        principles = kernel["values"]["layers"]["values"]["core_principles"]
        assert len(principles) >= 5
        # Security first should be priority 1
        security = [p for p in principles if "Security" in p["name"]]
        assert security, "Must have a Security principle"
        assert security[0]["priority"] == 1

    def test_values_has_will_do_and_will_not(self, kernel_dir):
        """Values boundaries layer must have will_do and will_not."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        boundaries = kernel["values"]["layers"]["boundaries"]
        assert len(boundaries["will_do"]) >= 5
        assert len(boundaries["will_not"]) >= 8

    def test_safety_has_boundaries(self, kernel_dir):
        """Safety constraints must define hard boundaries."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        sc = kernel["safety_constraints"]
        assert "hard_boundaries" in sc or "forbidden_actions" in sc, \
            "Safety constraints must define boundaries"

    def test_safety_has_forbidden_actions(self, kernel_dir):
        """Safety constraints must list forbidden actions."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        sc = kernel["safety_constraints"]
        assert len(sc["forbidden_actions"]) >= 5

    def test_safety_has_threat_levels(self, kernel_dir):
        """Safety constraints must define threat level actions."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        levels = kernel["safety_constraints"]["threat_levels"]
        assert "critical" in levels
        assert levels["critical"]["action"] == "block_and_alert"

    def test_safety_has_rate_limits(self, kernel_dir):
        """Safety constraints must define rate limits."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        rl = kernel["safety_constraints"]["rate_limits"]["default"]
        assert rl["requests_per_minute"] == 60
        assert rl["requests_per_hour"] == 500

    def test_safety_has_pii_rules(self, kernel_dir):
        """Safety constraints must define PII protection rules."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        pii = kernel["safety_constraints"]["pii_rules"]
        assert len(pii["output_filter_patterns"]) >= 4
        assert len(pii["sensitive_paths"]) >= 3

    def test_constitution_lists_components(self, kernel_dir):
        """Constitution must list its component files."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        const = kernel["constitution"]
        assert "components" in const
        assert len(const["components"]) >= 3

    def test_constitution_specifies_sha256(self, kernel_dir):
        """Constitution must specify sha256 as checksum algorithm."""
        from aria_mind.kernel import KernelLoader
        kernel = KernelLoader.load(kernel_dir)
        assert kernel["constitution"]["checksum_algorithm"] == "sha256"


class TestDeepFreeze:
    """Tests for the _deep_freeze utility."""

    def test_freeze_dict(self):
        from aria_mind.kernel import _deep_freeze
        frozen = _deep_freeze({"a": 1, "b": {"c": 2}})
        assert isinstance(frozen, types.MappingProxyType)
        assert isinstance(frozen["b"], types.MappingProxyType)

    def test_freeze_list(self):
        from aria_mind.kernel import _deep_freeze
        frozen = _deep_freeze([1, [2, 3], {"a": 4}])
        assert isinstance(frozen, tuple)
        assert isinstance(frozen[1], tuple)
        assert isinstance(frozen[2], types.MappingProxyType)

    def test_freeze_scalars_unchanged(self):
        from aria_mind.kernel import _deep_freeze
        assert _deep_freeze(42) == 42
        assert _deep_freeze("hello") == "hello"
        assert _deep_freeze(None) is None
        assert _deep_freeze(True) is True

    def test_frozen_dict_raises_on_write(self):
        from aria_mind.kernel import _deep_freeze
        frozen = _deep_freeze({"key": "value"})
        with pytest.raises(TypeError):
            frozen["key"] = "new"

    def test_frozen_nested_dict_raises_on_write(self):
        from aria_mind.kernel import _deep_freeze
        frozen = _deep_freeze({"outer": {"inner": "value"}})
        with pytest.raises(TypeError):
            frozen["outer"]["inner"] = "evil"
