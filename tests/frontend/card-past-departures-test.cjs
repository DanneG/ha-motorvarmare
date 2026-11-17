/* Run with Playwright available on NODE_PATH and Chrome installed. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:390,height:900}});
    await page.clock.install({time:new Date('2026-11-11T08:10:00Z')});
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:'motorvarmare-card{display:block;width:360px;--primary-text-color:#eee;--secondary-text-color:#aaa;--card-background-color:#222;--secondary-background-color:#333;--divider-color:#555;--primary-color:#03a9d3;--text-primary-color:#fff}'});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{});
      customElements.define('ha-icon',class extends HTMLElement{});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const entries=[
        {departure:'2026-11-11T06:50:00Z',start:'2026-11-11T05:46:00Z',end:'2026-11-11T07:20:00Z',source:'Planerad',uid:'past',removable:true},
        {departure:'2026-11-11T08:00:00Z',start:'2026-11-11T06:56:00Z',end:'2026-11-11T08:30:00Z',source:'Kalender'},
        {departure:'2026-11-11T09:00:00Z',start:'2026-11-11T08:00:00Z',end:'2026-11-11T09:30:00Z',source:'Planerad',uid:'next',removable:true},
      ];
      const states={
        'sensor.car_status':{entity_id:'sensor.car_status',state:'waiting_to_start',attributes:{friendly_name:'Bil status',control_entities:{heater_switch:'switch.car',calendar:'calendar.car'},schedule_7_days:entries}},
        'calendar.car':{entity_id:'calendar.car',state:'off',attributes:{}},
        'switch.car':{entity_id:'switch.car',state:'off',attributes:{}},
      };
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(){},async callWS(){}};
      const card=document.createElement('motorvarmare-card');card.setConfig({status_entity:'sensor.car_status'});card.hass=window.hass;document.body.appendChild(card);
    });
    const card=page.locator('motorvarmare-card');
    const past=card.locator('[data-mobile-departure="2026-11-11T06:50:00Z"]');
    const after=card.locator('[data-mobile-departure="2026-11-11T08:00:00Z"]');
    const future=card.locator('[data-mobile-departure="2026-11-11T09:00:00Z"]');
    await card.locator('.mobile-day').first().waitFor({state:'visible'});
    assert.match(await past.innerText(),/Beräknad värmning[\s\S]*Avresa passerad/);
    assert.match(await past.getAttribute('class'),/is-past/);
    assert.equal(await past.locator('[data-remove-uid="past"]').count(),1,'Past events remain editable and removable');
    assert.match(await after.innerText(),/Beräknad värmning[\s\S]*Avresa passerad/);
    assert.doesNotMatch(await after.getAttribute('class'),/is-past/,'Post-departure period stays visually current until estimated stop');
    assert.doesNotMatch(await future.innerText(),/Avresa passerad/);
    assert.doesNotMatch(await future.getAttribute('class'),/is-past/);
    await page.clock.fastForward(21*60*1000);
    assert.match(await after.getAttribute('class'),/is-past/,'Calendar updates when post-departure period ends even without a HA state update');
    await page.evaluate(()=>{window.hass.language='en';window.hass.locale.language='en';document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await after.innerText(),/Estimated heating[\s\S]*Departure passed/);
    await card.locator('#open-calendar').click();
    const modal=card.locator('#calendar-expanded');
    const block=modal.locator('[data-departure="2026-11-11T08:00:00Z"]');
    assert.match(await block.getAttribute('class'),/is-past/,'Expanded grid also marks completed events');
    assert.match(await block.getAttribute('aria-label'),/Departure passed/);
    await modal.locator('.cal-agenda summary').click();
    assert.match(await modal.locator('.cal-agenda').innerText(),/Departure passed/);
    console.log('PASS: past departures, post-departure interval, clock transitions and both languages');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
