# Security Policy

## Supported versions

Only the latest release is supported.

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

Report them through
[GitHub private security advisories](https://github.com/heibench/prusaslicer-py/security/advisories/new).

Include what you did, what happened, what you expected, and the versions of
this package and of PrusaSlicer involved.

## Scope

This package runs PrusaSlicer as a subprocess and reads what it writes. Two
things follow that are worth stating.

**Arguments reach an external program.** Values passed to `slice_model` and
`additional_args` become arguments to the engine. They are passed as an argv
list, never through a shell, so there is no shell injection — but a caller who
forwards untrusted input is still choosing what a local binary is asked to do.

**Flatpak filesystem grants.** When the engine is a Flatpak, the directories of
the input and output paths are granted to the sandbox with `--filesystem`. Only
those directories, never `--filesystem=host`. A caller who passes paths in
sensitive locations is granting the engine access to them.

Vulnerabilities in PrusaSlicer itself belong
[upstream](https://github.com/prusa3d/PrusaSlicer/security).
