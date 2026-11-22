"""Tests for patchpal-sandbox network restrictions (allowed URLs, ports, flag validation)."""

import re
import subprocess
import sys
from unittest import mock

import pytest

from patchpal.cli import sandbox


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://api.openai.com", ("api.openai.com", 443)),
        ("https://api.openai.com/v1", ("api.openai.com", 443)),
        ("http://example.com", ("example.com", 80)),
        ("http://host.containers.internal:11434", ("host.containers.internal", 11434)),
        ("http://localhost:8000/v1", ("localhost", 8000)),
        ("api.groq.com", ("api.groq.com", 443)),  # No scheme: treated as https
        ("http://host:99999", (None, None)),  # Invalid port
        ("https://", (None, None)),  # No hostname
    ],
)
def test_parse_allowed_url(url, expected):
    assert sandbox.parse_allowed_url(url) == expected


def _firewall_lines(script):
    """Return the iptables ACCEPT lines for allowed IPs, with the port loop expanded."""
    return re.findall(r"iptables -A OUTPUT -d \$IP -p tcp --dport \$PORT -j ACCEPT", script)


def test_script_pairs_each_host_with_its_port():
    script = sandbox.build_network_restriction_script(
        ["https://api.openai.com", "http://host.containers.internal:11434"]
    )
    # The firewall rule uses the per-entry port, not a hardcoded 443
    assert _firewall_lines(script)
    assert "--dport 443 -j ACCEPT" not in script
    # Each hostname is resolved without its scheme or port
    assert 'HOSTNAME="api.openai.com"' in script
    assert 'HOSTNAME="host.containers.internal"' in script
    # Resolved IPs are recorded with their port
    assert '$IP 443"' in script
    assert '$IP 11434"' in script


def test_script_skips_unsafe_hostnames(capsys):
    """Hostnames go into a shell script, so anything with shell metacharacters is skipped."""
    script = sandbox.build_network_restriction_script(['https://evil.com";rm -rf ~;"'])
    assert "evil.com" not in script
    assert "rm -rf" not in script
    assert "Skipping invalid allowed URL" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="requires bash")
def test_script_allowed_ip_loop_produces_ip_port_pairs():
    """Run the resolution and allow loops in bash with stubbed getent/iptables."""
    script = sandbox.build_network_restriction_script(
        ["https://api.openai.com", "http://host.containers.internal:11434"],
        block_dns_exfil=False,
    )
    # Keep only the part between URL resolution and the final DROP rules
    start = script.index('ALLOWED_IPS=""')
    end = script.index("# Allow established connections")
    body = script[start:end]
    # Drop the resolver and localhost sections, which need /etc/resolv.conf
    body = re.sub(r"# Install iptables.*?(?=# Allow each resolved IP)", "", body, flags=re.S)

    stub = """
getent() {
    case "$2" in
        api.openai.com) echo "1.1.1.1 api.openai.com"; echo "1.1.1.2 api.openai.com" ;;
        host.containers.internal) echo "10.0.2.2 host.containers.internal" ;;
    esac
}
iptables() { echo "RULE $*"; }
"""
    result = subprocess.run(["bash", "-c", stub + body], capture_output=True, text=True, check=True)
    rules = [line for line in result.stdout.splitlines() if line.startswith("RULE")]
    assert rules == [
        "RULE -A OUTPUT -d 1.1.1.1 -p tcp --dport 443 -j ACCEPT",
        "RULE -A OUTPUT -d 1.1.1.2 -p tcp --dport 443 -j ACCEPT",
        "RULE -A OUTPUT -d 10.0.2.2 -p tcp --dport 11434 -j ACCEPT",
    ]


def test_ollama_and_vllm_endpoints_are_detected(monkeypatch):
    for key in list(sandbox.os.environ):
        if key.endswith(
            ("_API_KEY", "_API_BASE", "_BASE_URL", "_ENDPOINT", "_API_TOKEN")
        ) or key.startswith("AWS_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OLLAMA_API_BASE", "http://host.containers.internal:11434")
    monkeypatch.setenv("HOSTED_VLLM_API_BASE", "http://10.0.0.5:8000")
    detected = sandbox.detect_llm_endpoints_from_env()
    assert "http://host.containers.internal:11434" in detected
    assert "http://10.0.0.5:8000" in detected


def test_restrict_network_with_host_network_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["patchpal-sandbox", "--restrict-network", "--host-network", "--", "--model", "x"],
    )
    with mock.patch.object(sandbox, "build_container_args") as build:
        with pytest.raises(SystemExit) as exc:
            sandbox.main()
    assert exc.value.code == 1
    build.assert_not_called()
    assert "can't be combined with --host-network" in capsys.readouterr().err


class _SandboxArgs:
    """Minimal stand-in for parsed sandbox args (unset options default to None)."""

    network = "bridge"
    env_file = None
    dev = False
    image = "ghcr.io/amaiya/patchpal-sandbox:latest"
    env = []
    volume = []

    def __getattr__(self, name):
        return None


@pytest.mark.parametrize(
    "var, value",
    [
        ("OLLAMA_API_BASE", "http://host.containers.internal:11434"),
        ("HOSTED_VLLM_API_BASE", "http://10.0.0.5:8000"),
    ],
)
def test_local_server_endpoints_reach_the_container(monkeypatch, var, value):
    """An endpoint the firewall allows is useless unless PatchPal in the container sees it."""
    monkeypatch.setenv(var, value)
    with (
        mock.patch.object(sandbox, "detect_runtime", return_value="podman"),
        mock.patch.object(sandbox, "ensure_podman_machine"),
    ):
        args, _ = sandbox.build_container_args(_SandboxArgs(), ["--model", "x"])
    assert f"{var}={value}" in args
