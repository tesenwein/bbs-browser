# Contributing to BBS Browser

Thanks for your interest in contributing! This project follows a simple git-flow style workflow.

## Branching model

- `main` — always deployable, tagged releases.
- `develop` — integration branch for the next release.
- Feature/fix branches — branch off `develop`, named `feat/...`, `fix/...`, `chore/...`.

## Workflow

1. Fork the repo and clone your fork.
2. Create a branch off `develop`:
   ```
   git checkout -b feat/my-change develop
   ```
3. Make your changes, following the existing code style.
4. Run tests and linters before pushing (see `Makefile` for available targets).
5. Open a pull request targeting `develop` (not `main`).
6. Fill out the PR template and link any related issues.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>
```

Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `style`, `perf`.

## Pull requests

- All PRs require at least one approving review before merge.
- Keep PRs focused — one logical change per PR.
- Update documentation and tests alongside code changes.

## Reporting bugs / requesting features

Please use the issue templates when opening a new issue so we have the context needed to help.

## Code of Conduct

By participating in this project you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
