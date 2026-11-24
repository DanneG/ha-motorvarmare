/* Run with Playwright on NODE_PATH and Chrome installed. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:440,height:1100}});
    await page.clock.setFixedTime(new Date('2026-11-06T10:00:00Z'));
    const errors=[];
    page.on('pageerror', error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:`body{margin:0;padding:16px;background:#1a1b1c;font-family:Roboto,Arial,sans-serif}motorvarmare-card{display:block;--primary-text-color:#e8eaed;--secondary-text-color:#b8c0cb;--card-background-color:#171717;--secondary-background-color:#292a2d;--divider-color:#3c4043;--primary-color:#03a9d3;--text-primary-color:#fff}`});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{connectedCallback(){Object.assign(this.style,{display:'block',background:'var(--card-background-color)',borderRadius:'15px'});}});
      customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent='♨';}});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.heater',start_now:'button.start',stop_now:'button.stop',calendar:'calendar.schedule',manual_departure:'datetime.manual',clear_departure:'button.clear',weekly_times:Array.from({length:7},(_,i)=>`time.car_${i}`),weekly_enabled:Array.from({length:7},(_,i)=>`switch.car_${i}`)};
      const states={
        'sensor.car_status':{entity_id:'sensor.car_status',state:'no_departure',attributes:{friendly_name:'Bil 1 Status',control_entities:controls,temperature:-4,current_duration_minutes:36,owned:false,schedule_7_days:[]}},
        'switch.heater':{entity_id:'switch.heater',state:'off',attributes:{}},
        'button.start':{entity_id:'button.start',state:'unknown',attributes:{}},
        'button.stop':{entity_id:'button.stop',state:'unknown',attributes:{}},
        'button.clear':{entity_id:'button.clear',state:'unknown',attributes:{}},
        'datetime.manual':{entity_id:'datetime.manual',state:'unknown',attributes:{}},
        'calendar.schedule':{entity_id:'calendar.schedule',state:'off',attributes:{}},
      };
      controls.weekly_times.forEach(id=>states[id]={entity_id:id,state:'07:00:00',attributes:{}});
      controls.weekly_enabled.forEach(id=>states[id]={entity_id:id,state:'off',attributes:{}});
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(){},async callWS(){}};
      const card=document.createElement('motorvarmare-card');
      card.setConfig({status_entity:'sensor.car_status',title:'Bil 1'}); card.hass=window.hass; document.body.appendChild(card);
      window.changeHistory=value=>{window.hass.states['sensor.car_status'].attributes.heating_history=value;card.hass={...window.hass};};
    });
    const card=page.locator('motorvarmare-card');
    await card.locator('[data-main-tab="energy"]').click();
    const toggle=card.locator('#history-toggle');
    assert.equal(await toggle.getAttribute('aria-expanded'),'true','History is visible by default');
    await toggle.click();
    assert.equal(await toggle.getAttribute('aria-expanded'),'false','History can be collapsed');
    await toggle.click();
    assert.match(await card.locator('.history-section').innerText(),/Uppdatera integrationen för att visa historiken/,'Older integrations should show update guidance');
    await page.evaluate(()=>window.changeHistory([]));
    assert.equal(await toggle.getAttribute('aria-expanded'),'true','Opening stays expanded on HA updates');
    assert.match(await card.locator('.history-section').innerText(),/Inga registrerade värmningar ännu/);
    const entries=[
      {start:'2026-11-06T07:00:00+01:00',end:'2026-11-06T08:15:00+01:00',duration_minutes:75,energy_kwh:1.25,complete:true},
      {start:'2026-11-05T22:30:00+01:00',end:'2026-11-06T00:00:00+01:00',duration_minutes:90,energy_kwh:null,complete:true},
      {start:null,end:'2026-11-04T09:30:00+01:00',duration_minutes:null,energy_kwh:null,complete:false},
    ];
    await page.evaluate(value=>window.changeHistory(value),entries);
    assert.equal(await card.locator('.history-entry').count(),3);
    const first=await card.locator('.history-entry').nth(0).innerText();
    assert.match(first,/fre 6 nov\. 2026 07:00.*08:15/);
    assert.match(first,/Gångtid: 1 tim 15 min/);
    assert.match(first,/Energi: 1,25 kWh/);
    const second=await card.locator('.history-entry').nth(1).innerText();
    assert.match(second,/tors? 5 nov\. 2026 22:30.*fre 6 nov\. 00:00/);
    assert.match(second,/Energi saknas/);
    const third=await card.locator('.history-entry').nth(2).innerText();
    assert.match(third,/Starttid saknas.*Av.*09:30/);
    assert.match(third,/Tidsuppgifter ofullständiga/);
    assert.doesNotMatch(third,/Gångtid:/,'A partial session must not imply an exact duration');
    if (process.env.MOTORVARMARE_HISTORY_PREVIEW_PATH) await page.screenshot({path:process.env.MOTORVARMARE_HISTORY_PREVIEW_PATH,fullPage:true});
    const extra=Array.from({length:12},(_,i)=>({start:'2026-11-04T07:00:00+01:00',end:'2026-11-04T07:36:00+01:00',duration_minutes:36,energy_kwh:i===0 ? 0 : 0.5,complete:true}));
    await page.evaluate(value=>window.changeHistory(value),extra);
    assert.equal(await card.locator('.history-entry').count(),10,'Only the first page is rendered initially');
    assert.match(await card.locator('.history-entry').first().innerText(),/Energi: 0,00 kWh/,'Zero energy is a valid measurement');
    await card.locator('#history-more').click();
    assert.equal(await card.locator('.history-entry').count(),12,'All remaining sessions are accessible');
    assert.equal(await card.locator('#history-more').count(),0);
    await page.evaluate(()=>{window.hass.locale.language='en';window.changeHistory([{start:null,end:null,duration_minutes:20,energy_kwh:null,complete:false}]);});
    assert.match(await card.locator('.history-section').innerText(),/Heating history/);
    assert.match(await card.locator('.history-entry').innerText(),/Start time unavailable/);
    assert.match(await card.locator('.history-entry').innerText(),/End time unavailable/);
    assert.match(await card.locator('.history-entry').innerText(),/Timing incomplete/);
    assert.match(await card.locator('.history-entry').innerText(),/Energy unavailable/);
    assert.doesNotMatch(await card.locator('.history-entry').innerText(),/Heating time: 20 min/);
    await page.evaluate(()=>window.changeHistory([{start:'2026-10-25T02:40:00+02:00',end:'2026-10-25T02:10:00+01:00',duration_minutes:30,energy_kwh:0.4,complete:true}]));
    assert.match(await card.locator('.history-entry').innerText(),/GMT\+2.*GMT\+1/,'Repeated local hours should identify their offsets');
    await page.setViewportSize({width:320,height:1000});
    assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'History must fit a narrow card');
    assert.deepEqual(errors,[]);
    console.log('PASS: history, partial readings, times, timezone, paging, mobile and translations');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
