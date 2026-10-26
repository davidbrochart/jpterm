# Releasing jpterm

Releases are prepared on `main` and published by
[`.github/workflows/publish.yml`](.github/workflows/publish.yml).
Pushing a matching version tag builds all workspace packages, publishes them to
PyPI, and creates a GitHub release from `CHANGELOG.md`.

The commands below use a POSIX shell and require Git, uv, and an authenticated
GitHub CLI (`gh`). On Windows, adjust virtual environment executable paths from
`bin/` to `Scripts/`.

## Prepare the versions

1. Switch to `main`, inspect `git status --short`, and update with
   `git pull --ff-only`. Preserve unrelated local files and changes.
2. Check the merged changes since the previous release and confirm that main's
   CI is green.
3. Update the application version in the root `pyproject.toml`.
4. Bump the version of every workspace package whose code or dependency
   declarations changed. Packages have independent versions; they do not all
   use jpterm's application version.
5. Update internal dependency requirements to require the new versions where
   needed, including the application's minimum plugin versions.

The workspace consists of `txl/` and the plugin packages included by
`[tool.uv.workspace]` in the root `pyproject.toml`. Respect its exclusions.

All current plugins pin an exact `txl` version. If shared `txl` code changes,
release a new `txl` version, update every plugin's pin, and bump each affected
plugin's version. This includes plugins whose implementation did not change:
their dependency metadata changed. Update jpterm's dependency minimums to match.

For example, v0.3.13 included `txl` 0.3.5, coordinated plugin patch releases,
and new minimum versions in jpterm's dependencies.

Add a `## VERSION` entry near the top of `CHANGELOG.md`, following the existing
format. Describe user-visible changes and list any accompanying package releases.
The GitHub release workflow extracts its notes from this heading; use the
numeric version without a leading `v`.

Before publishing, confirm that every newly assigned package/version pair is
unused on PyPI. Do not rely on `skip-existing` to publish changed code under an
existing version.

## Validate the release

Run the test suite and build all packages, rather than only the application:

```bash
uv run --group test pytest tests -q
RELEASE_DIST=$(mktemp -d)
uv build --all-packages --out-dir "$RELEASE_DIST"
git diff --check
```

Also run the repository's pre-commit checks:

```bash
pre-commit run --all-files --hook-stage=manual
```

Check that the wheels and source distributions have the intended versions and
that their internal requirements are compatible. Use a fresh build directory so
artifacts from older releases are not mixed in.

Test installation from the built wheels in a separate environment. Replace the
example version with the release being prepared:

```bash
VERSION=0.3.13
RELEASE_CHECK=$(mktemp -d)
uv venv "$RELEASE_CHECK"
uv pip install --python "$RELEASE_CHECK/bin/python" \
  --find-links "$RELEASE_DIST" "jpterm==$VERSION"
uv pip check --python "$RELEASE_CHECK/bin/python"
"$RELEASE_CHECK/bin/jpterm" --help
```

Run smoke tests from outside the checkout so imports come from the installed
wheels. With a disposable notebook, check kernel startup, execution across
separate CLI calls, and kernel shutdown. Stop test kernels afterward.

## Commit, check CI, and tag

Review and stage only the intended release changes. Keep local notebooks,
runtime databases, checkpoints, and other unrelated files out of the commit.

```bash
git commit -m "Release v$VERSION"
git push origin main
gh run list --branch main --workflow test --limit 1
```

Verify that the listed run targets the release commit, then wait for all jobs:

```bash
gh run watch TEST_RUN_ID --exit-status
```

If CI fails, inspect the failed logs, fix the cause, and push a new commit.
Wait for that commit's CI to pass before tagging. If a package's implementation
changes during this step, rebuild and revalidate its release artifacts.

Create the tag at the exact tested commit:

```bash
git tag -a "$VERSION" TESTED_COMMIT_SHA -m "Release v$VERSION"
git push origin "refs/tags/$VERSION"
```

Use `0.3.13`, **not** `v0.3.13`: the publishing workflow's tag patterns do not
accept a leading `v`. Pushing this tag starts publication; it is not a dry run.

## Verify publication

```bash
gh run list --workflow publish --limit 1
gh run watch PUBLISH_RUN_ID --exit-status
gh release view "$VERSION"
```

Confirm that the publishing run targets the intended tag and commit. It has
three jobs:

1. Build wheels and source distributions for all workspace packages.
2. Upload them to PyPI using trusted publishing and the `release` environment.
   Already published, unchanged package versions are skipped.
3. Create the GitHub release using the changelog entry. Alpha, beta, and release
   candidate tags are marked as prereleases.

Check that jpterm and every accompanying new package version are visible on
PyPI, and that the GitHub release has the expected notes. Where practical,
verify installation of the published application in a fresh environment too.

If publication fails, inspect `gh run view PUBLISH_RUN_ID --log-failed` before
retrying. For unchanged artifacts, rerun the failed jobs:

```bash
gh run rerun PUBLISH_RUN_ID --failed
```

`skip-existing` allows already uploaded artifacts to be skipped. Changed
artifacts require new package versions. Do not move an already published release
tag or attempt to replace files that PyPI has accepted.
