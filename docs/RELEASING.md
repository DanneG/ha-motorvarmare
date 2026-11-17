# Release checklist

Perform these steps for **every release**, including maintenance releases:

1. Update the integration version in `custom_components/motorvarmare/manifest.json` and prepare accurate release notes in English. Describe the actual changes, any upgrade steps and relevant limitations. Update the Swedish and English documentation when needed.
2. Regenerate and inspect both card screenshots using the current bundled card and fictional data. Do not use screenshots of a real Home Assistant installation. From the repository root, with Node.js installed:

   ```sh
   npm install --no-save playwright@1.62.1
   npx playwright install chromium
   node scripts/render-screenshots.cjs
   ```

   Review `docs/demo-card-en.png` and `docs/demo-card-sv.png`, adjust the fictional fixture if necessary, and include both resulting images in the release commit. `MOTORVARMARE_BROWSER` can optionally point to a Chromium executable.
3. Run `python -m unittest discover -s tests`, check the bundled JavaScript with `node --check custom_components/motorvarmare/www/ha-motorvarmare-card.js`, and run the frontend tests with Playwright and Chromium available. For the frontend tests, set `MOTORVARMARE_BROWSER` to `require('playwright').chromium.executablePath()` and run each `tests/frontend/*.cjs` file with Node.js.
4. Push the release commit and verify that both HACS validation and hassfest pass without ignored checks. Create the GitHub release from that tested commit with the version tag and prepared notes.
5. Check the release page and installation or upgrade instructions. If a catalog submission is awaiting review, update its release and validation links as appropriate.
