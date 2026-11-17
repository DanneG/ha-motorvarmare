/* Check current-period summaries without inventing missing energy or costs. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');

async function main(){
  const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page=await browser.newPage({viewport:{width:320,height:800}});
    await page.clock.setFixedTime(new Date('2026-11-06T10:00:00Z'));
    await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><motorvarmare-card></motorvarmare-card></body></html>');
    await page.addStyleTag({content:'body{margin:0;font-family:Arial}motorvarmare-card,ha-card{display:block}motorvarmare-card{--primary-text-color:#111;--secondary-text-color:#555;--primary-color:#007f95;--card-background-color:#fff;--secondary-background-color:#eee;--divider-color:#bbb}'});
    await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{});});
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const attrs={friendly_name:'Bil',control_entities:{heater_switch:'switch.heater'},temperature:-5,heating_history:[],cost_configured:true};
      window.hass={states:{'sensor.status':{state:'waiting',attributes:attrs},'switch.heater':{state:'off',attributes:{}}},language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(){},async callWS(){return {events:[]}}};
      const card=document.querySelector('motorvarmare-card');card.setConfig({status_entity:'sensor.status'});card.hass=window.hass;
      window.updateTotals=value=>{attrs.history_energy_totals=value;card.hass={...window.hass};};
    });
    const card=page.locator('motorvarmare-card');
    await card.locator('[data-main-tab="energy"]').click();
    await page.evaluate(()=>window.updateTotals({
      daily:[{period_start:'2026-11-05',energy_kwh:55,sessions:1},{period_start:'2026-11-06',energy_kwh:1.25,estimated_cost:2.5,cost_currency:'SEK',sessions:1}],
      weekly:[{period_start:'2026-11-02',energy_kwh:2,incomplete:true,cost_incomplete:true,sessions:2}],
      monthly:[{period_start:'2026-10-01',energy_kwh:99,sessions:1}],
    }));
    const cards=card.locator('.period-card');
    assert.equal(await cards.count(),3);
    assert.match(await cards.nth(0).innerText(),/I dag[\s\S]*1,25 kWh[\s\S]*2,50 SEK/);
    assert.doesNotMatch(await cards.nth(0).innerText(),/55/,'Older daily periods must not be shown as today');
    assert.match(await cards.nth(1).innerText(),/Den här veckan[\s\S]*2,00 kWh[\s\S]*Ofullständigt underlag[\s\S]*Kostnad saknas eller är ofullständig/);
    assert.match(await cards.nth(2).innerText(),/Den här månaden[\s\S]*Ingen uppgift/,'Missing current month must never use an old value or a fabricated zero');
    assert.doesNotMatch(await cards.nth(2).innerText(),/99|0,00 kWh/);
    await page.clock.setFixedTime(new Date('2026-11-06T23:30:00Z'));
    await page.evaluate(()=>window.updateTotals({daily:[{period_start:'2026-11-06',energy_kwh:3,sessions:1},{period_start:'2026-11-07',energy_kwh:0,sessions:1}],weekly:[],monthly:[]}));
    assert.match(await cards.nth(0).innerText(),/0,00 kWh/,'A real zero is valid and the day follows the Home Assistant time zone');
    assert.doesNotMatch(await cards.nth(0).innerText(),/3,00 kWh/);
    await page.evaluate(()=>{window.hass.locale.language='en';window.updateTotals({daily:[],weekly:[],monthly:[]});});
    assert.match(await cards.nth(0).innerText(),/Today[\s\S]*No data/);
    assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Summary must fit narrow screens');
    console.log('PASS: current local periods, partial costs, missing data and genuine zero');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
