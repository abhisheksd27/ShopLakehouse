# ShopLakehouse — Build Progress

## Objective

Build an e-commerce analytics platform locally, then validate and
deploy it on AWS.

## Progress

| Step | Task | Status |
|---|---|---|
| 1 | Docker hello-world | Verified |
| 2 | Project directory | Verified |
| 3 | Git initialized on main | Verified |
| 4 | .gitignore configured | Verified |
| 5 | Python 3.11 virtual environment | Verified: Python 3.11.15 runs from the project .venv |
| 6 | Initial folders and progress document | Verified: folders created; Git detects docs and src |

## Decisions

- Develop and test locally first.
- Validate AWS-specific behavior in a cloud development environment.
- Keep credentials and virtual environments out of Git.
- Update documentation after each verified step.

## Issues resolved

macOS metadata appeared in Git as ._.git.
Adding ._* to .gitignore excluded these files.

## Pending documentation

Save the architecture plan in docs/architecture.md.