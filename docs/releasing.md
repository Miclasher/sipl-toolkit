# Releasing sipl-toolkit

Versions follow [SemVer](https://semver.org/). Releases are cut from `main`.

## Procedure

1. Make sure CI is green on `main`.
2. Bump the version in **both** `pyproject.toml` (`[project] version`) and
   `src/sipl/__init__.py` (`__version__`). Check with `python scripts/check_version.py`.
3. Update `CHANGELOG.md`: rename `[Unreleased]` content into a new `[X.Y.Z] - date`
   section, add a fresh empty `[Unreleased]`, and update the compare links.
4. Commit: `Release X.Y.Z`.
5. Dry run locally:
   ```
   python -m pip install build twine
   python -m build && twine check dist/*
   ```
   Optionally upload to TestPyPI: `twine upload --repository testpypi dist/*`
   (needs a TestPyPI account/token), then install from it in a fresh venv.
6. Tag and push:
   ```
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin main vX.Y.Z
   ```

## What the workflows do

- `ci.yml` (push to main, pull requests): lint (ruff, mypy), tests on Python
  3.11-3.14 with coverage >= 80%, package build + `twine check` + wheel smoke test,
  and a syntax check of the VS Code extension.
- `release.yml` (tag `vX.Y.Z`): builds sdist and wheel, fails if the tag differs from the
  package version, creates a GitHub Release (auto-generated notes plus the CHANGELOG
  section) with `dist/*` attached, then optionally publishes to PyPI.

## PyPI trusted publishing setup (one time)

1. Create the project on PyPI (or add a *pending publisher* at
   https://pypi.org/manage/account/publishing/ for the name `sipl-toolkit`).
2. Publisher settings: owner = your GitHub user/org, repository = this repo,
   workflow = `release.yml`, environment = `pypi`.
3. In GitHub: Settings -> Environments -> create `pypi` (optionally require reviewers).
4. In GitHub: Settings -> Secrets and variables -> Actions -> Variables -> add
   `PUBLISH_TO_PYPI` = `true`. Without it, the publish job is skipped.
5. Replace `OWNER/REPO` in the CHANGELOG compare links.
