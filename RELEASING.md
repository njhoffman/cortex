# Releasing approved updates

Every user-approved update receives a changelog entry, a SemVer bump, passing checks, a build, a commit, an annotated `vMAJOR.MINOR.PATCH` tag, and a push to GitHub. Do not release unrelated work. The first release is `v0.1.0`.

Choose `patch` for compatible fixes or maintenance and `minor` for compatible features. Reserve `major` for breaking stable interfaces; document breaking changes explicitly during pre-1.0 development.

For the next approved update:

```sh
# Write the approved change's release notes in a Markdown file outside the repo.
just bump patch /tmp/cortex-release-notes.md
# Review and stage only the approved changes, including version, lockfile,
# changelog, and the completed TASK.md checklist.
git add <approved-files>
just release
```

`just release` rejects unstaged tracked changes, an existing tag, or a version/changelog mismatch. It runs lint, tests, and packaging; commits the staged update; creates an annotated tag; and atomically pushes the current branch and tag to `origin`. It does not force-push. If a network push fails, the local commit and tag remain available to inspect and push again; do not bump again for a retry.

GitHub CI tests supported Python versions. Pushing a `v*` tag starts a separate release workflow that verifies the tag/package/changelog versions, tests, rebuilds the wheel and source distribution, and attaches both with checksums to the GitHub release. GitHub credentials and permission to push workflow files are required.

The CLI and catalog schema are the public interfaces. Package version is defined once in `pyproject.toml` and read from installed package metadata by the CLI; the lockfile, changelog entry, and Git tag must match it. Upstream cheatsheet revisions are recorded independently in each catalog manifest.
