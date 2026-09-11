"""Start one owned loopback API + Worker with synthetic, revocable identities.

The readiness JSON prints the URL and local credential file path, never the
credential itself. Ctrl+C revokes identities, removes their file and stops
only this server's Worker. No user project or existing service is modified.
"""
from run_workbench_test_server import main

if __name__ == "__main__":
    main()
