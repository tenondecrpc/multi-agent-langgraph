"""Tests for ephemeral cluster bootstrap utilities."""

import pytest

from backend.testing.cluster_bootstrap import ClusterConfig, EphemeralCluster, get_cluster_config

pytestmark = pytest.mark.chaos


class TestClusterConfig:
    """Tests for ClusterConfig dataclass."""

    def test_default_values(self):
        """ClusterConfig should have sensible defaults."""
        config = ClusterConfig()
        assert config.cluster_type == "kind"
        assert config.cluster_name == "chaos-test"
        assert config.namespace == "chaos-test"
        assert config.helm_chart_path == "../../helm"

    def test_custom_values(self):
        """ClusterConfig should accept custom values."""
        config = ClusterConfig(
            cluster_type="k3d",
            cluster_name="my-cluster",
            namespace="my-namespace",
            helm_chart_path="/path/to/chart",
        )
        assert config.cluster_type == "k3d"
        assert config.cluster_name == "my-cluster"
        assert config.namespace == "my-namespace"
        assert config.helm_chart_path == "/path/to/chart"


class TestEphemeralCluster:
    """Tests for EphemeralCluster class."""

    def test_init_with_default_config(self):
        """EphemeralCluster should initialize with default config."""
        cluster = EphemeralCluster()
        assert cluster.config.cluster_type == "kind"
        assert cluster._created is False

    def test_init_with_custom_config(self):
        """EphemeralCluster should accept custom config."""
        config = ClusterConfig(cluster_type="k3d", cluster_name="test")
        cluster = EphemeralCluster(config)
        assert cluster.config.cluster_type == "k3d"
        assert cluster.config.cluster_name == "test"

    def test_unsupported_cluster_type(self):
        """EphemeralCluster should raise on unsupported cluster type."""
        config = ClusterConfig(cluster_type="minikube")
        cluster = EphemeralCluster(config)
        with pytest.raises(ValueError, match="Unsupported cluster type"):
            cluster.create()


class TestGetClusterConfig:
    """Tests for get_cluster_config function."""

    def test_returns_cluster_config(self):
        """get_cluster_config should return a ClusterConfig instance."""
        config = get_cluster_config()
        assert isinstance(config, ClusterConfig)
