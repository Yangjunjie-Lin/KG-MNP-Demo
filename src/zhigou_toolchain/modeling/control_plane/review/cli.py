"""Authenticated review CLI; decision authority belongs to ApplicationService."""
from zhigou_toolchain.services.resource_cli import main as resource_main


def main(argv=None):
    return resource_main("review", argv)
