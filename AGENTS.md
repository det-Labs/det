# Repository Guidelines for det-core

## Release & Publishing Workflow
- **Automatic PyPI Deployment**: When publishing a new version, creating a formal release on GitHub (e.g. tag `v*` via `https://github.com/det-Labs/det/releases`) automatically triggers `.github/workflows/publish.yml`. This workflow runs unit tests, builds wheels and sdist, validates with twine, and publishes the package to PyPI via Trusted Publishing.
- **GitHub Release Display**: Creating the GitHub release updates the "Latest Release" sidebar and badge on GitHub's landing page.
- **Landing Page Deployment**: Pushing updates to `main` automatically triggers `.github/workflows/pages.yml`, which deploys the static `site/` folder to GitHub Pages.
