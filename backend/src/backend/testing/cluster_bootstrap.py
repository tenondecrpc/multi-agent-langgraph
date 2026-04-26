"""Ephemeral cluster bootstrap utilities for chaos testing.

Provides helpers to create and destroy kind/k3d clusters for running
chaos scenarios against a realistic Kubernetes deployment.
"""

import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClusterConfig:
    """Configuration for an ephemeral test cluster."""

    cluster_type: str = "kind"
    cluster_name: str = "chaos-test"
    namespace: str = "chaos-test"
    helm_chart_path: str = "../../helm"
    kubeconfig: str | None = None


class EphemeralCluster:
    """Manages an ephemeral Kubernetes cluster for chaos testing."""

    def __init__(self, config: ClusterConfig | None = None):
        self.config = config or ClusterConfig()
        self._created = False

    def create(self) -> None:
        """Create the ephemeral cluster and deploy the Helm chart."""
        if self.config.cluster_type == "kind":
            self._create_kind_cluster()
        elif self.config.cluster_type == "k3d":
            self._create_k3d_cluster()
        else:
            raise ValueError(f"Unsupported cluster type: {self.config.cluster_type}")

        self._create_namespace()
        self._deploy_helm_chart()
        self._created = True

    def destroy(self) -> None:
        """Destroy the ephemeral cluster."""
        if not self._created:
            return

        if self.config.cluster_type == "kind":
            self._delete_kind_cluster()
        elif self.config.cluster_type == "k3d":
            self._delete_k3d_cluster()

        self._created = False

    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a subprocess command."""
        logger.info("Running: %s", " ".join(cmd))
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def _create_kind_cluster(self) -> None:
        """Create a kind cluster."""
        self._run([
            "kind", "create", "cluster",
            "--name", self.config.cluster_name,
            "--wait", "120s",
        ])

    def _delete_kind_cluster(self) -> None:
        """Delete a kind cluster."""
        self._run(["kind", "delete", "cluster", "--name", self.config.cluster_name])

    def _create_k3d_cluster(self) -> None:
        """Create a k3d cluster."""
        self._run([
            "k3d", "cluster", "create", self.config.cluster_name,
            "--wait",
        ])

    def _delete_k3d_cluster(self) -> None:
        """Delete a k3d cluster."""
        self._run(["k3d", "cluster", "delete", self.config.cluster_name])

    def _create_namespace(self) -> None:
        """Create the test namespace."""
        self._run(["kubectl", "create", "namespace", self.config.namespace])

    def _deploy_helm_chart(self) -> None:
        """Deploy the Helm chart to the cluster."""
        self._run([
            "helm", "install", "langgraph-dev-squad",
            self.config.helm_chart_path,
            "--namespace", self.config.namespace,
            "--set", "chaosTesting.enabled=true",
            "--wait",
        ])

    def is_ready(self) -> bool:
        """Check if the cluster and deployment are ready."""
        try:
            result = self._run([
                "kubectl", "rollout", "status",
                "deployment/langgraph-dev-squad-api",
                "--namespace", self.config.namespace,
                "--timeout", "30s",
            ], check=False)
            return result.returncode == 0
        except Exception:
            return False


def get_cluster_config() -> ClusterConfig:
    """Build cluster config from environment variables."""
    return ClusterConfig(
        cluster_type=os.getenv("CHAOS_CLUSTER_TYPE", "kind"),
        cluster_name=os.getenv("CHAOS_CLUSTER_NAME", "chaos-test"),
        namespace=os.getenv("CHAOS_NAMESPACE", "chaos-test"),
        helm_chart_path=os.getenv("HELM_CHART_PATH", "../../helm"),
    )
