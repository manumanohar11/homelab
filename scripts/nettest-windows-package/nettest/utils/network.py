"""Network interface utilities."""

import os
import socket
from typing import List, Dict, Optional, Any


def list_interfaces() -> List[Dict[str, Any]]:
    """
    List available network interfaces with their addresses.

    Returns:
        List of dicts with interface info:
        - name: Interface name (e.g., "eth0")
        - up: Whether interface is up
        - addresses: List of IP addresses
    """
    interfaces = []

    # Try using netifaces if available (more reliable)
    try:
        import netifaces
        for iface_name in netifaces.interfaces():
            iface_info = {
                "name": iface_name,
                "up": True,  # netifaces doesn't provide this directly
                "addresses": [],
            }

            addrs = netifaces.ifaddresses(iface_name)

            # IPv4 addresses
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    if "addr" in addr:
                        iface_info["addresses"].append(addr["addr"])

            # IPv6 addresses
            if netifaces.AF_INET6 in addrs:
                for addr in addrs[netifaces.AF_INET6]:
                    if "addr" in addr:
                        # Remove scope ID from link-local addresses
                        ipv6 = addr["addr"].split("%")[0]
                        iface_info["addresses"].append(ipv6)

            interfaces.append(iface_info)

        return interfaces

    except ImportError:
        pass

    # Fallback: Read from /sys/class/net on Linux
    if os.path.exists("/sys/class/net"):
        for iface_name in os.listdir("/sys/class/net"):
            iface_info = {
                "name": iface_name,
                "up": False,
                "addresses": [],
            }

            # Check if interface is up
            operstate_path = f"/sys/class/net/{iface_name}/operstate"
            if os.path.exists(operstate_path):
                try:
                    with open(operstate_path) as f:
                        state = f.read().strip()
                        iface_info["up"] = state == "up"
                except IOError:
                    pass

            # Try to get address using socket
            try:
                import fcntl
                import struct

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # SIOCGIFADDR = 0x8915
                result = fcntl.ioctl(
                    sock.fileno(),
                    0x8915,
                    struct.pack('256s', iface_name[:15].encode('utf-8'))
                )
                ip = socket.inet_ntoa(result[20:24])
                iface_info["addresses"].append(ip)
                sock.close()
            except (IOError, OSError, ImportError):
                pass

            interfaces.append(iface_info)

    return interfaces


def get_interface_ip(interface_name: str) -> Optional[str]:
    """
    Get the primary IPv4 address of a network interface.

    Args:
        interface_name: Name of the interface (e.g., "eth0")

    Returns:
        IPv4 address string, or None if not found
    """
    # Try netifaces first
    try:
        import netifaces
        addrs = netifaces.ifaddresses(interface_name)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                if "addr" in addr:
                    return addr["addr"]
        return None
    except (ImportError, ValueError):
        pass

    # Fallback using socket
    try:
        import fcntl
        import struct

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        result = fcntl.ioctl(
            sock.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', interface_name[:15].encode('utf-8'))
        )
        ip = socket.inet_ntoa(result[20:24])
        sock.close()
        return ip
    except (IOError, OSError, ImportError):
        pass

    return None


def validate_interface(interface_name: str) -> bool:
    """
    Check if a network interface exists and is valid.

    Args:
        interface_name: Name of the interface to check

    Returns:
        True if interface exists, False otherwise
    """
    # Check in /sys/class/net on Linux
    if os.path.exists(f"/sys/class/net/{interface_name}"):
        return True

    # Try netifaces
    try:
        import netifaces
        return interface_name in netifaces.interfaces()
    except ImportError:
        pass

    # Try listing available interfaces
    interfaces = list_interfaces()
    return any(iface["name"] == interface_name for iface in interfaces)


def get_default_interface() -> Optional[str]:
    """
    Get the name of the default network interface.

    Returns:
        Interface name, or None if cannot determine
    """
    # Try netifaces
    try:
        import netifaces
        gateways = netifaces.gateways()
        default = gateways.get('default', {})
        if netifaces.AF_INET in default:
            return default[netifaces.AF_INET][1]
    except (ImportError, KeyError):
        pass

    # Fallback: Parse /proc/net/route on Linux
    route_file = "/proc/net/route"
    if os.path.exists(route_file):
        try:
            with open(route_file) as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 2 and fields[1] == "00000000":
                        return fields[0]
        except IOError:
            pass

    return None
