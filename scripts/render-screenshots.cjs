/* Render documentation screenshots using only the fixed, fictional data below.
 *
 * Run with Playwright available and a Playwright Chromium browser installed:
 *   node scripts/render-screenshots.cjs
 * Optionally set MOTORVARMARE_BROWSER to a Chromium executable.
 * Images are written to docs/demo-card-sv.png and docs/demo-card-en.png.
 */
const { chromium } = require('playwright');
const path = require('node:path');

const project = path.resolve(__dirname, '..');
const cardFile = path.join(project, 'custom_components', 'motorvarmare', 'www', 'ha-motorvarmare-card.js');
const browserPath = process.env.MOTORVARMARE_BROWSER;

async function render(browser, lang) {
  const page = await browser.newPage({ viewport: { width: 680, height: 1000 }, deviceScaleFactor: 1, locale: lang === 'sv' ? 'sv-SE' : 'en-GB', colorScheme: 'dark' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.clock.setFixedTime(new Date('2026-11-05T08:25:00Z'));
  await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body></body></html>');
  await page.addStyleTag({content:`
    body { margin: 0; padding: 24px; background: #151719; font-family: Roboto, Arial, sans-serif; }
    motorvarmare-card { display: block; max-width: 560px; margin: auto;
      --primary-text-color: #edf1f3; --secondary-text-color: #a4adb4;
      --card-background-color: #202426; --secondary-background-color: #2a3033;
      --divider-color: #3b4347; --primary-color: #00accf; --text-primary-color: #fff; }
  `});
  await page.evaluate(() => {
    customElements.define('ha-card', class extends HTMLElement { connectedCallback() { this.style.display = 'block'; } });
    customElements.define('ha-icon', class extends HTMLElement {
      connectedCallback() {
        if (this.shadowRoot) return;
        this.attachShadow({mode:'open'}).innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M5 11h14v8H5zM8 8c-2-2 2-3 0-5m4 5c-2-2 2-3 0-5m4 5c-2-2 2-3 0-5M8 19v2m8-2v2"/></svg>';
      }
    });
  });
  await page.addScriptTag({path: cardFile});
  await page.evaluate(({language}) => {
    // This fixture does not connect to Home Assistant, a calendar or any real plug.
    const controls = { heater_switch:'switch.demo', stop_now:'button.demo_stop', extend_30:'button.demo_extend', cable_test:'button.demo_test', manual_departure:'datetime.demo_manual', clear_departure:'button.demo_clear', weekly_times:['time.demo_monday'], weekly_enabled:['switch.demo_monday'], calendar:'calendar.demo', start_now:'button.demo_start' };
    const events = [
      { departure:'2026-11-05T09:30:00Z', start:'2026-11-05T08:00:00Z', end:'2026-11-05T10:00:00Z', source:'Planerad', uid:'demo-1', removable:true, duration_minutes:90 },
      { departure:'2026-11-06T09:00:00Z', start:'2026-11-06T07:30:00Z', end:'2026-11-06T09:30:00Z', source:'Planerad', uid:'demo-2', removable:true, duration_minutes:90 },
    ];
    const attributes = {
      cable_test_enabled:true, cable_test_result:'connected', cable_test_at:'2026-11-04T20:00:08Z',
      friendly_name:'Demo status', control_entities:controls, temperature:-5,
      current_duration_minutes:90, next_departure:events[0].departure, planned_start:events[0].start,
      post_departure_minutes:30, source:'Planerad', schedule_7_days:events,
      owned:true, active_scheduled_departure:events[0].departure, active_started_at:'2026-11-05T08:00:00Z', active_measurement_started_at:'2026-11-05T08:00:00Z',
      active_until:'2026-11-05T10:00:00Z', active_max_until:'2026-11-05T12:00:00Z', can_extend:true,
      power_sensor_configured:true, energy_sensor_configured:true, power_w:780,
      session_energy_kwh:0.32, active_session_cost:0.64, active_session_currency:'SEK',
      active_power_samples:[
        {at:'2026-11-05T08:00:00Z',watts:600}, {at:'2026-11-05T08:05:00Z',watts:720},
        {at:'2026-11-05T08:10:00Z',watts:800}, {at:'2026-11-05T08:15:00Z',watts:790},
        {at:'2026-11-05T08:20:00Z',watts:780}, {at:'2026-11-05T08:25:00Z',watts:780},
      ],
    };
    const states = {
      'sensor.demo':{entity_id:'sensor.demo',state:'heating',attributes},
      'switch.demo':{entity_id:'switch.demo',state:'on',attributes:{}},
      'button.demo_stop':{entity_id:'button.demo_stop',state:'unknown',attributes:{}},
      'button.demo_extend':{entity_id:'button.demo_extend',state:'unknown',attributes:{}},
      'button.demo_start':{entity_id:'button.demo_start',state:'unknown',attributes:{}},
      'datetime.demo_manual':{state:'unknown',attributes:{}},
      'button.demo_clear':{state:'unknown',attributes:{}},
      'button.demo_test':{state:'unknown',attributes:{}},
      'calendar.demo':{entity_id:'calendar.demo',state:'off',attributes:{}},
    };
    const hass = {states, language, locale:{language}, config:{time_zone:'Europe/Stockholm'},
      async callService(){}, async callWS(){return {events:[], calendar_error:false};}};
    const card = document.createElement('motorvarmare-card');
    card.setConfig({status_entity:'sensor.demo',title:language === 'sv' ? 'Exempelbil' : 'Example car'});
    card.hass = hass;
    document.body.appendChild(card);
  }, {language:lang});
  await page.locator('motorvarmare-card').waitFor();
  await page.locator('motorvarmare-card .active-progress').waitFor();
  await page.locator('[data-main-tab="settings"]').click();
  await page.locator('.cable-check').waitFor();
  if (errors.length) throw new Error(errors.join('\n'));
  await page.screenshot({path:path.join(project,'docs',`demo-card-${lang}.png`),fullPage:true});
  await page.close();
}

(async () => {
  const browser = await chromium.launch({headless:true, ...(browserPath ? {executablePath:browserPath} : {})});
  try { await render(browser,'sv'); await render(browser,'en'); }
  finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
