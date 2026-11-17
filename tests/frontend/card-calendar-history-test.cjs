/* Run with Playwright on NODE_PATH and Chrome installed. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:390,height:1000}});
    await page.clock.setFixedTime(new Date('2026-11-06T12:00:00Z'));
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:`body{margin:0;padding:16px;background:#181818}motorvarmare-card{display:block;--primary-text-color:#eee;--secondary-text-color:#bbb;--card-background-color:#171717;--secondary-background-color:#292929;--divider-color:#444;--primary-color:#03a9d3;--text-primary-color:white}`});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{connectedCallback(){this.style.display='block';}});
      customElements.define('ha-icon',class extends HTMLElement{});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.heater',start_now:'button.start',stop_now:'button.stop',calendar:'calendar.schedule'};
      const states={
        'sensor.car_status':{entity_id:'sensor.car_status',state:'no_departure',attributes:{friendly_name:'Bil Status',control_entities:controls,temperature:-4,current_duration_minutes:60,owned:false,cost_configured:true,
          schedule_7_days:[
            {departure:'2026-11-06T07:50:00+01:00',start:'2026-11-06T06:50:00+01:00',end:'2026-11-06T08:20:00+01:00',source:'Planerad',uid:'one',removable:true},
            {departure:'2026-11-06T08:00:00+01:00',start:'2026-11-06T07:00:00+01:00',end:'2026-11-06T08:30:00+01:00',source:'Kalender'},
          ],
          heating_history:[
            {start:'2026-11-06T07:00:00+01:00',end:'2026-11-06T08:30:00+01:00',duration_minutes:90,energy_kwh:1.25,estimated_cost:2.75,cost_currency:'SEK',complete:true},
            {start:null,end:'2026-11-06T10:00:00+01:00',duration_minutes:null,energy_kwh:null,estimated_cost:null,cost_currency:'SEK',complete:false},
            {start:'2026-11-05T23:00:00+01:00',end:'2026-11-06T00:00:00+01:00',duration_minutes:60,energy_kwh:0,estimated_cost:0,cost_currency:'SEK',complete:true},
            {start:'2026-11-06T22:00:00Z',end:'2026-11-06T23:30:00Z',duration_minutes:90,energy_kwh:9.99,estimated_cost:88.88,cost_currency:'SEK',complete:true},
            {start:'2026-11-05T07:00:00+01:00',end:'2026-11-05T08:00:00+01:00',duration_minutes:60,energy_kwh:7.77,complete:true},
            {start:'2026-11-06T10:00:00+01:00',end:null,duration_minutes:null,energy_kwh:6.66,complete:false},
          ]}},
        'switch.heater':{entity_id:'switch.heater',state:'off',attributes:{}},
        'button.start':{entity_id:'button.start',state:'unknown',attributes:{}},
        'button.stop':{entity_id:'button.stop',state:'unknown',attributes:{}},
        'calendar.schedule':{entity_id:'calendar.schedule',state:'off',attributes:{}},
      };
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(){},async callWS(){}};
      const card=document.createElement('motorvarmare-card');
      card.setConfig({status_entity:'sensor.car_status',title:'Bil 1'}); card.hass=window.hass; document.body.appendChild(card);
    });
    const card=page.locator('motorvarmare-card');
    await card.locator('[data-mobile-day="2026-11-06"]').click();
    const recorded=card.locator('.calendar-history');
    const entries=recorded.locator('.calendar-history-entry');
    assert.equal(await entries.count(),3,'Show observed sessions ending on the selected local day only');
    let text=await recorded.innerText();
    assert.match(text,/1,25 kWh/);
    assert.match(text,/2,75\s*SEK/);
    assert.match(text,/0,00 kWh/,'Zero is a valid measurement');
    assert.match(text,/Energi saknas/,'Missing measurements are not zero');
    assert.match(text,/Kostnad saknas/,'Missing cost is clearly distinguished from zero');
    assert.match(text,/Tidsuppgifter ofullständiga/,'A partial session is clearly marked');
    assert.doesNotMatch(text,/9,99 kWh|7,77 kWh|6,66 kWh|88,88/,'Do not assign other days or undated sessions to this day');
    const scheduled=await card.locator('.mobile-event').allInnerTexts();
    assert.equal(scheduled.length,2);
    for (const value of scheduled) assert.doesNotMatch(value,/1,25 kWh|2,75\s*SEK/,'Do not guess which overlapping departure caused the observed session');
    if (process.env.MOTORVARMARE_CALENDAR_HISTORY_PREVIEW_PATH) await page.screenshot({path:process.env.MOTORVARMARE_CALENDAR_HISTORY_PREVIEW_PATH,fullPage:true});
    await card.locator('[data-mobile-day="2026-11-07"]').click();
    assert.equal(await entries.count(),1,'UTC times are grouped using the Home Assistant timezone');
    text=await recorded.innerText();
    assert.match(text,/9,99 kWh/);
    assert.match(text,/88,88\s*SEK/);
    assert.doesNotMatch(text,/1,25 kWh|2,75\s*SEK/);
    await page.evaluate(()=>{window.hass.language='en';window.hass.locale.language='en';document.querySelector('motorvarmare-card').hass={...window.hass};});
    text=await recorded.innerText();
    assert.match(text,/9[.,]99 kWh/,'History values remain available in English');
    await page.setViewportSize({width:1200,height:1000});
    const historyDay=card.locator('#calendar-history-day');
    assert.equal(await historyDay.isVisible(),true,'Day selector is visible in the desktop calendar');
    await historyDay.selectOption('2026-11-06');
    assert.equal(await entries.count(),3,'Desktop day selection switches to the matching recorded sessions');
    assert.match(await recorded.innerText(),/1[.,]25 kWh/);
    await historyDay.selectOption('2026-11-08');
    assert.equal(await entries.count(),0);
    assert.match(await recorded.innerText(),/No recorded heating sessions on this day/,'Empty days are explained');
    await page.setViewportSize({width:390,height:1000});
    await card.locator('#open-calendar').click();
    const modal=card.locator('#calendar-expanded');
    const modalDay=modal.locator('#calendar-history-day');
    assert.equal(await modalDay.isVisible(),true,'Expanded calendar day selector remains available on a narrow screen');
    await modalDay.selectOption('2026-11-06');
    assert.equal(await modal.locator('.calendar-history-entry').count(),3,'Expanded calendar day selection updates recorded sessions');
    assert.match(await modal.locator('.calendar-history').innerText(),/1[.,]25 kWh/);
    assert.deepEqual(errors,[]);
    console.log('PASS: daily recorded heating, missing readings, overlapping departures, costs, local day, desktop and expanded calendar');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
