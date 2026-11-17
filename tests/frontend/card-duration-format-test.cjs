/* Duration labels should be legible and consistent in both supported languages. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page=await browser.newPage({viewport:{width:390,height:850},isMobile:true,hasTouch:true});
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.clock.setFixedTime(new Date('2026-11-05T09:30:00Z'));
    await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><motorvarmare-card></motorvarmare-card></body></html>');
    await page.addStyleTag({content:'motorvarmare-card,ha-card{display:block}'});
    await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{});});
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.heater',calendar:'calendar.car',start_now:'button.start',stop_now:'button.stop',weekly_times:[],weekly_enabled:[]};
      const attrs={friendly_name:'Bil status',control_entities:controls,temperature:-5,current_duration_minutes:90,duration_minutes:90,next_departure:'2026-11-05T14:00:00Z',planned_start:'2026-11-05T11:30:00Z',schedule_7_days:[],heating_history:[]};
      const states={'sensor.status':{entity_id:'sensor.status',state:'waiting_to_start',attributes:attrs},'switch.heater':{state:'off',attributes:{}},'calendar.car':{state:'off',attributes:{}},'button.start':{state:'unknown',attributes:{}},'button.stop':{state:'unknown',attributes:{}}};
      const card=document.querySelector('motorvarmare-card');
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(){},async callWS(){return {events:[]};}};
      window.update=(patch={},language='sv')=>{Object.assign(attrs,patch);window.hass.language=language;window.hass.locale={language};card.hass={...window.hass};};
      card.setConfig({status_entity:'sensor.status'});card.hass=window.hass;
    });
    const card=page.locator('motorvarmare-card');
    const cases=[
      [0,'0 min','0 min'],[30,'30 min','30 min'],[59,'59 min','59 min'],[59.6,'1 tim','1 h'],
      [60,'1 tim','1 h'],[61,'1 tim 1 min','1 h 1 min'],
      [90,'1 tim 30 min','1 h 30 min'],[180,'3 tim','3 h']
    ];
    for(const [minutes,sv,en] of cases) {
      for(const [language,wanted] of [['sv',sv],['en',en]]) {
        await page.evaluate(({minutes,language})=>window.update({current_duration_minutes:minutes},language),{minutes,language});
        const summary=(await card.locator('.summary-metrics > span').nth(1).locator('strong').innerText()).trim();
        assert.equal(summary,wanted,`${language} summary for ${minutes} minutes`);
        if(minutes>0) {
          const action=await card.locator('.quick-actions').first().innerText();
          assert.ok(action.includes(wanted),`${language} start explanation must show ${wanted}: ${action}`);
        }
      }
    }
    // Missing temperature-based duration is not silently shown as zero.
    await page.evaluate(()=>window.update({current_duration_minutes:null,duration_minutes:null,next_departure:null,planned_start:null},'sv'));
    const unavailable=await card.locator('.summary-metrics').innerText();
    assert.match(unavailable,/Värmetid\s*–/);
    assert.equal(await card.locator('#start-now').isDisabled(),true);
    await page.evaluate(()=>window.update({current_duration_minutes:-1},'sv'));
    assert.match(await card.locator('.summary-metrics').innerText(),/Värmetid\s*–/);
    assert.equal(await card.locator('#start-now').isDisabled(),true);

    // Subsequent heating, the waiting countdown and stored history all use the
    // same duration conventions; a short actual session remains "under 1 min".
    await page.evaluate(()=>window.update({current_duration_minutes:90,next_departure:'2026-11-05T14:00:00Z',planned_start:'2026-11-05T11:30:00Z',post_departure_minutes:90,heating_history:[
      {start:'2026-11-04T06:00:00Z',end:'2026-11-04T07:30:00Z',duration_minutes:90,complete:true,energy_kwh:1},
      {start:'2026-11-04T05:00:00Z',end:'2026-11-04T05:00:10Z',duration_minutes:0.16,complete:true,energy_kwh:0}
    ]},'sv'));
    assert.match(await card.locator('.summary-metrics').innerText(),/Efter avresa\s*1 tim 30 min/);
    assert.match(await card.locator('.status').first().innerText(),/Startar om\s*2 tim/);
    await card.locator('[data-main-tab="energy"]').click();
    assert.match(await card.locator('.history-entry').nth(0).innerText(),/Gångtid:\s*1 tim 30 min/);
    assert.match(await card.locator('.history-entry').nth(1).innerText(),/under 1 min/i);
    await page.evaluate(()=>window.update({},'en'));
    assert.match(await card.locator('.history-entry').nth(0).innerText(),/Heating time:\s*1 h 30 min/i);
    assert.deepEqual(errors,[]);
    console.log('PASS: Swedish and English heating durations, countdowns, missing data and history');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exit(1)});
