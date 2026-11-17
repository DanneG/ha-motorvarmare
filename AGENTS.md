# Release requirements

For every release, regenerate the documentation screenshots from the current bundled dashboard card using fictional example data. Inspect the resulting images and update the images and their descriptions in the repository before tagging the release. Never use real Home Assistant account, calendar, location or device data in public screenshots.

For every release, write and publish accurate English release notes describing the changes, upgrade steps and any relevant limitations. Keep the Swedish documentation up to date as needed. Run the relevant tests and ensure the HACS and hassfest validation checks pass before publishing.

Follow the steps in [docs/RELEASING.md](docs/RELEASING.md), including regenerating both screenshots before creating the release tag.
