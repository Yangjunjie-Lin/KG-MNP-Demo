"""Authenticated lifecycle resource CLI; no client-supplied reviewer roles."""
from zhigou_toolchain.services.resource_cli import main as resource_main


def main(argv=None):
    return resource_main("lifecycle", argv)
