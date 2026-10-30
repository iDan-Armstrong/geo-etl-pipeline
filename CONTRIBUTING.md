# Contributing

## Workflow

- Branch from `main`: `feat/<topic>`, `fix/<topic>`, or `docs/<topic>`.
- Keep PRs small and single-purpose; a reviewable PR beats a complete one.
- Every PR runs lint + tests on three Python versions; green CI is a merge
  precondition, not a suggestion.
- Commits in imperative mood ("add quarantine sink"), body explains *why* when
  it isn't obvious.

## Adding a transform

1. Write the function in `src/geoetl/transform.py` with the `@register("name")`
   decorator and a docstring that states its CRS expectations.
2. Add tests in `tests/test_transform.py` — including the failure modes.
3. Document it in the README's transform list if user-facing.

## Adding a QA rule

Same pattern in `src/geoetl/qa.py` (`_EVALUATORS`) and `tests/test_qa.py`.
A rule must fail *rows*, not raise — raising is for config errors.

## Releases

Tag `vX.Y.Z` on `main`; CI builds and attaches artifacts to the GitHub release.
Update CHANGELOG.md by moving "unreleased" items under the new version.
