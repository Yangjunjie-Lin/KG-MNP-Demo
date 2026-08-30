# Plugin trust and security

Python plugins are installed code chosen and trusted by the operator. Once
explicitly enabled, they execute with the operating-system permissions of the
KG-MNP process. The SDK cannot prevent malicious Python from reading files,
opening sockets or spawning processes; KG-MNP makes no sandbox claim.

The controls that do exist are fail-closed metadata discovery, no automatic
import, an explicit external allowlist, offline/network and deterministic
selection policy, exact distribution/entry-point checks, declared-file
snapshots, finite requests, typed responses and Core-only artifact authority.
Domain Packs remain data-only and Workspaces are never searched for `.py`
files. Listing and doctor commands do not import external implementation code.

`NETWORK` is excluded by the Prompt 3 offline policy. `NONDETERMINISTIC` is
excluded by strict mode. These declarations guide selection; they do not make
a dishonest plugin safe. Deploy untrusted providers in an operating-system
isolation boundary maintained outside this repository.
