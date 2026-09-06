# Contributing

## Getting set up

```sh
just setup          # sync the environment from the committed lockfile
just lock           # re-resolve uv.lock after changing a dependency
just check          # format check + lint + typecheck
just test           # the suite
```

`just check && just test` is what CI runs. Run it before every commit, and
never bypass hooks.

## Tests and the engine

Most of the suite runs without PrusaSlicer installed. The tests that need the
real engine request the `engine` fixture, which **skips** when it is absent —
a missing engine is an environment fault, not a verdict on the code.

Set `PRUSASLICER_PY_REQUIRE_ENGINE=1` to turn that skip into a hard failure.
CI does this on the runners that install the engine, so "the engine is missing"
cannot masquerade as a green run.

```sh
just test-engine    # the whole suite, engine required (POSIX shells)
```

If you have PrusaSlicer installed, please run it and report what happens. The
engine is installed several different ways — PATH, Flatpak, AppImage, macOS
bundle, Windows installer — and discovery has been wrong about at least one of
them before.

## The CLI surface data

`scripts/01_helps/` and everything derived from it are **not committed**: they
are PrusaSlicer's own output and this repository is Apache-2.0 (D8). Regenerate
with:

```sh
just capture-cli    # needs PrusaSlicer installed
just extract-cli
```

The extraction tests skip without that corpus, and say so.

## Conventions

- Conventional Commits: `type(scope): description`, imperative, lowercase, no
  trailing period, subject ≤ 72 characters.
- One logical change per commit; branch and open a pull request.
- Decisions with consequences go in [`docs/DECISIONS.md`](docs/DECISIONS.md),
  numbered. Do not relitigate a numbered decision — supersede it.
- A check that cannot fail is not a check. If you add one, break the thing it
  checks and watch it go red before you trust it.
