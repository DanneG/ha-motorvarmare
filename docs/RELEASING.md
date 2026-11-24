# Release checklist

1. Set `version` in `custom_components/motorvarmare/manifest.json`.
2. Write English release notes with changes, upgrade steps and relevant limitations. Update both READMEs where needed.
3. Regenerate both screenshots from the bundled card using **fictional data**. Inspect the images, update their descriptions and include both images in the release commit.
4. Run the Python and browser tests below. Push the commit and wait for **behavior**, **hacs** and **hassfest** to pass.
5. Tag that commit, publish the release notes and verify the release page and upgrade instructions. Update links in any pending catalog submission as needed.

## Screenshots and tests

Run from the repository root. `MOTORVARMARE_BROWSER` can point to a local Chromium executable.

```sh
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
export MOTORVARMARE_BROWSER="$(node -p "require('playwright').chromium.executablePath()")"

node scripts/render-screenshots.cjs
python -m unittest discover -s tests
node --check custom_components/motorvarmare/www/ha-motorvarmare-card.js
for test in tests/frontend/*.cjs; do node "$test" || exit 1; done
```

Review `docs/demo-card-en.png` and `docs/demo-card-sv.png` before tagging.
