"""Unit tests for nettest ping parsing."""

import pytest
from nettest.tests.ping import run_ping_test
from nettest.models import PingResult


class TestPingSuccess:
    """Tests for successful ping output parsing."""

    def test_ping_success_parses_statistics(self, mocker):
        """Parse successful ping output with all statistics."""
        ping_output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.3 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=11.8 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=118 time=12.1 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 11.800/12.067/12.300/0.205 ms
"""
        mock_run = mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3)

        assert result.success is True
        assert result.error == ""
        assert result.target == "8.8.8.8"
        assert result.target_name == "Google DNS"
        assert result.min_ms == 11.8
        assert result.avg_ms == 12.067
        assert result.max_ms == 12.3
        assert result.jitter_ms == 0.205
        assert result.packet_loss == 0.0
        assert result.samples == [12.3, 11.8, 12.1]
        mock_run.assert_called_once()

    def test_ping_success_with_ipv4_flag(self, mocker):
        """Verify IPv4 flag is passed to ping command."""
        ping_output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=10.0 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 10.000/10.000/10.000/0.000 ms
"""
        mock_run = mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        run_ping_test("8.8.8.8", "Google DNS", count=1, ip_version=4)

        call_args = mock_run.call_args[0][0]
        assert "-4" in call_args

    def test_ping_success_with_ipv6_flag(self, mocker):
        """Verify IPv6 flag is passed to ping command."""
        ping_output = """PING 2001:4860:4860::8888 56 data bytes
64 bytes from 2001:4860:4860::8888: icmp_seq=1 ttl=118 time=15.0 ms

--- 2001:4860:4860::8888 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 15.000/15.000/15.000/0.000 ms
"""
        mock_run = mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        run_ping_test("2001:4860:4860::8888", "Google DNS IPv6", count=1, ip_version=6)

        call_args = mock_run.call_args[0][0]
        assert "-6" in call_args

    def test_ping_success_with_interface(self, mocker):
        """Verify interface flag is passed to ping command."""
        ping_output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=10.0 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 10.000/10.000/10.000/0.000 ms
"""
        mock_run = mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        run_ping_test("8.8.8.8", "Google DNS", count=1, interface="eth0")

        call_args = mock_run.call_args[0][0]
        assert "-I" in call_args
        assert "eth0" in call_args


class TestPingPacketLoss:
    """Tests for ping output with packet loss."""

    def test_ping_partial_packet_loss(self, mocker):
        """Parse output with partial packet loss."""
        ping_output = """PING 192.168.1.100 (192.168.1.100) 56(84) bytes of data.
64 bytes from 192.168.1.100: icmp_seq=1 ttl=64 time=5.2 ms
64 bytes from 192.168.1.100: icmp_seq=3 ttl=64 time=5.8 ms
64 bytes from 192.168.1.100: icmp_seq=5 ttl=64 time=6.1 ms

--- 192.168.1.100 ping statistics ---
5 packets transmitted, 3 received, 40% packet loss, time 4005ms
rtt min/avg/max/mdev = 5.200/5.700/6.100/0.373 ms
"""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        result = run_ping_test("192.168.1.100", "Local Server", count=5)

        assert result.success is True
        assert result.packet_loss == 40.0
        assert result.min_ms == 5.2
        assert result.avg_ms == 5.7
        assert result.max_ms == 6.1
        assert len(result.samples) == 3

    def test_ping_high_packet_loss(self, mocker):
        """Parse output with high packet loss (90%)."""
        ping_output = """PING 10.0.0.1 (10.0.0.1) 56(84) bytes of data.
64 bytes from 10.0.0.1: icmp_seq=7 ttl=64 time=25.3 ms

--- 10.0.0.1 ping statistics ---
10 packets transmitted, 1 received, 90% packet loss, time 9012ms
rtt min/avg/max/mdev = 25.300/25.300/25.300/0.000 ms
"""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        result = run_ping_test("10.0.0.1", "Router", count=10)

        assert result.success is True
        assert result.packet_loss == 90.0
        assert result.samples == [25.3]


class TestPingTimeout:
    """Tests for ping timeout and unreachable scenarios."""

    def test_ping_host_unreachable(self, mocker):
        """Handle network unreachable error."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "connect: Network is unreachable")
        )

        result = run_ping_test("192.168.255.1", "Unreachable Host", count=3)

        assert result.success is False
        assert "Network unreachable" in result.error
        assert "Check your network connection" in result.error

    def test_ping_dns_failure(self, mocker):
        """Handle DNS resolution failure."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "ping: invalid.hostname.test: Name or service not known")
        )

        result = run_ping_test("invalid.hostname.test", "Invalid Host", count=3)

        assert result.success is False
        assert "DNS resolution failed" in result.error

    def test_ping_temporary_dns_failure(self, mocker):
        """Handle temporary DNS resolution failure."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "ping: host.example.com: Temporary failure in name resolution")
        )

        result = run_ping_test("host.example.com", "Temp DNS Fail", count=3)

        assert result.success is False
        assert "DNS resolution failed" in result.error

    def test_ping_command_timeout(self, mocker):
        """Handle command timeout."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(-1, "", "Command timed out")
        )

        result = run_ping_test("slow.host.test", "Slow Host", count=3)

        assert result.success is False
        assert "timed out" in result.error


class TestPing100PercentLoss:
    """Tests for 100% packet loss scenarios."""

    def test_ping_100_percent_loss_with_stats(self, mocker):
        """Handle 100% packet loss with statistics line present."""
        ping_output = """PING 10.255.255.1 (10.255.255.1) 56(84) bytes of data.

--- 10.255.255.1 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2004ms
"""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, ping_output, "")
        )

        result = run_ping_test("10.255.255.1", "Dead Host", count=3)

        # No stats pattern match (no rtt line), no times
        assert result.success is False
        assert result.packet_loss == 100.0
        assert result.samples == []
        assert result.avg_ms == 0.0

    def test_ping_100_percent_loss_with_exit_code_1(self, mocker):
        """Handle 100% packet loss with non-zero exit code but stdout present."""
        ping_output = """PING 192.168.99.99 (192.168.99.99) 56(84) bytes of data.

--- 192.168.99.99 ping statistics ---
5 packets transmitted, 0 received, 100% packet loss, time 4032ms
"""
        # ping returns exit code 1 when there's packet loss
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, ping_output, "")
        )

        result = run_ping_test("192.168.99.99", "Offline Host", count=5)

        assert result.packet_loss == 100.0
        assert result.samples == []


class TestPingErrorHandling:
    """Tests for command failure and error handling."""

    def test_ping_command_not_found(self, mocker):
        """Handle ping command not found."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(-1, "", "Command not found: ping")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3)

        assert result.success is False
        assert "ping not found" in result.error
        assert "apt install" in result.error

    def test_ping_permission_denied(self, mocker):
        """Handle permission denied error."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "ping: socket: Operation not permitted")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3)

        assert result.success is False
        assert "Permission denied" in result.error
        assert "sudo" in result.error

    def test_ping_interface_bind_error(self, mocker):
        """Handle interface binding error."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "ping: SO_BINDTODEVICE eth99: No such device")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3, interface="eth99")

        assert result.success is False
        assert "Cannot bind to interface" in result.error

    def test_ping_invalid_argument_error(self, mocker):
        """Handle invalid argument error for interface."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "ping: invalid argument: eth99")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3, interface="eth99")

        assert result.success is False
        assert "Cannot bind to interface" in result.error

    def test_ping_generic_error(self, mocker):
        """Handle unrecognized error message."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "Some unknown error occurred")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3)

        assert result.success is False
        assert result.error == "Some unknown error occurred"

    def test_ping_empty_stderr_error(self, mocker):
        """Handle error with empty stderr."""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(1, "", "")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3)

        assert result.success is False
        assert "Ping failed" in result.error


class TestPingEdgeCases:
    """Tests for edge cases in ping parsing."""

    def test_ping_parses_time_with_less_than_sign(self, mocker):
        """Parse ping output with time<1 ms format."""
        ping_output = """PING localhost (127.0.0.1) 56(84) bytes of data.
64 bytes from localhost (127.0.0.1): icmp_seq=1 ttl=64 time<1 ms
64 bytes from localhost (127.0.0.1): icmp_seq=2 ttl=64 time<1 ms
64 bytes from localhost (127.0.0.1): icmp_seq=3 ttl=64 time<1 ms

--- localhost ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2002ms
rtt min/avg/max/mdev = 0.015/0.023/0.035/0.008 ms
"""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        result = run_ping_test("localhost", "Localhost", count=3)

        assert result.success is True
        # time<1 matches as time=1 due to regex
        assert len(result.samples) == 3
        assert all(t == 1.0 for t in result.samples)

    def test_ping_manual_stats_calculation_when_summary_missing(self, mocker):
        """Calculate stats manually when rtt summary line is missing."""
        # Output without the rtt min/avg/max/mdev line
        ping_output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=10.0 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=20.0 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=118 time=15.0 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
"""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=3)

        assert result.success is True
        assert result.min_ms == 10.0
        assert result.max_ms == 20.0
        assert result.avg_ms == 15.0  # (10 + 20 + 15) / 3
        # Jitter calculated as average of consecutive differences: (|20-10| + |15-20|) / 2 = 7.5
        assert result.jitter_ms == 7.5
        assert result.samples == [10.0, 20.0, 15.0]

    def test_ping_single_sample_jitter_is_zero(self, mocker):
        """Ensure jitter is 0 when only one sample exists."""
        ping_output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.5 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
"""
        mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        result = run_ping_test("8.8.8.8", "Google DNS", count=1)

        assert result.success is True
        assert result.min_ms == 12.5
        assert result.max_ms == 12.5
        assert result.avg_ms == 12.5
        # No jitter with single sample (jitter_ms stays at default 0.0)
        assert result.jitter_ms == 0.0

    def test_ping_verifies_command_timeout_calculation(self, mocker):
        """Verify timeout is calculated as count * 3 + 10."""
        ping_output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=10.0 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 10.000/10.000/10.000/0.000 ms
"""
        mock_run = mocker.patch(
            "nettest.tests.ping.run_command",
            return_value=(0, ping_output, "")
        )

        run_ping_test("8.8.8.8", "Google DNS", count=5)

        # Timeout should be count * 3 + 10 = 5 * 3 + 10 = 25
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 25
