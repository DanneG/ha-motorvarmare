/* Regression coverage for the compact card, forecasts, pause and prices. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');

async function main(){
  const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try{
    const page=await browser.newPage({viewport:{width:390,height:700},isMobile:true,hasTouch:true});
    await page.clock.setFixedTime(new Date('2026-11-05T09:30:00Z'));
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body><div style="height:600px">Before</div></body></html>');
    await page.addStyleTag({content:'body{margin:0}motorvarmare-card{display:block;width:380px}ha-card{display:block}'});
    await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{});});
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.heater',calendar:'calendar.car',start_now:'button.start',stop_now:'button.stop',skip_next:'button.skip',automation_paused:'switch.paused',pause_until:'datetime.pause',manual_departure:'datetime.manual',clear_departure:'button.clear',weekly_times:[],weekly_enabled:[]};
      const attributes={friendly_name:'Bil status',control_entities:controls,temperature:-5,current_duration_minutes:90,next_departure:'2026-11-05T12:00:00Z',planned_start:'2026-11-05T10:30:00Z',weather_enabled:true,schedule_query_supported:true,schedule_7_days:[],cost_configured:true,heating_history:[{start:'2026-11-04T06:00:00Z',end:'2026-11-04T07:00:00Z',duration_minutes:60,energy_kwh:1.2,complete:true,estimated_cost:3.0,cost_currency:'SEK',cost_basis:'sensor_at_end'}],history_energy_totals:{daily:[{period_start:'2026-11-04',energy_kwh:1.2,incomplete:false,estimated_cost:3,cost_currency:'SEK',cost_incomplete:true}],weekly:[],monthly:[],has_older:{}}};
      const states={'sensor.status':{entity_id:'sensor.status',state:'waiting_to_start',attributes},'switch.heater':{state:'off',attributes:{}},'calendar.car':{state:'off',attributes:{}},'button.start':{state:'unknown',attributes:{}},'button.stop':{state:'unknown',attributes:{}},'button.skip':{state:'unknown',attributes:{}},'switch.paused':{state:'off',attributes:{}},'datetime.pause':{state:'unknown',attributes:{}},'datetime.manual':{state:'unknown',attributes:{}},'button.clear':{state:'unknown',attributes:{}}};
      window.calls=[];window.schedules=[];window.pendingForecast=[];window.deferForecast=false;
      const forecast={departure:'2026-11-05T12:00:00Z',start:'2026-11-05T09:30:00Z',end:'2026-11-05T12:00:00Z',source:'Kalender',duration_minutes:150,temperature_source:'forecast',forecast_temperature:-15};
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(domain,service,data){window.calls.push({domain,service,data});},async callWS(message){window.schedules.push(message);if(window.deferForecast)return new Promise(resolve=>window.pendingForecast.push(resolve));return {events:[forecast],calendar_error:false};}};
      const card=document.createElement('motorvarmare-card');card.setConfig({status_entity:'sensor.status'});card.hass=window.hass;document.body.appendChild(card);
    });
    const card=page.locator('motorvarmare-card');
    await page.waitForFunction(()=>document.querySelector('motorvarmare-card').shadowRoot.textContent.includes('Prognos'));
    const todayEvent=card.locator('[data-mobile-departure="2026-11-05T12:00:00Z"]');
    assert.match(await todayEvent.innerText(),/Prognos.*−?15|Prognos.*-15/,'Forecast is clearly identified');
    assert.match(await card.locator('.status').innerText(),/Startar om/);
    assert.ok((await page.evaluate(()=>window.schedules)).some(item=>item.type==='motorvarmare/get_schedule'));
    // A real HA update keeps the live calendar and page scroll anchor intact.
    await page.evaluate(()=>{window.scrollTo(0,650);window.anchor=document.querySelector('motorvarmare-card').shadowRoot.querySelector('.calendar');window.oldScroll=window.scrollY;window.hass.states['sensor.status'].attributes.temperature=-6;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await page.evaluate(()=>window.anchor===document.querySelector('motorvarmare-card').shadowRoot.querySelector('.calendar')),true);
    assert.ok(Math.abs(await page.evaluate(()=>window.scrollY-window.oldScroll))<30,'HA updates should not jump to page top');
    // Moving between new tabs retains an unsaved recurring event draft.
    await card.locator('#new-departure').click();
    await card.locator('#calendar-time').fill('14:45');
    await card.locator('#calendar-summary').fill('Eget arbetspass');
    await card.locator('#repeat-frequency').selectOption('WEEKLY');
    assert.equal(await card.locator('#window-next').isDisabled(),true,'A week change must not discard an unsaved departure');
    assert.match(await card.locator('.calendar').innerText(),/Spara eller avbryt ändringen/);
    await card.locator('[data-main-tab="energy"]').click();
    assert.equal(await card.locator('[data-main-panel="calendar"]').isVisible(),false);
    if (await card.locator('#history-toggle').getAttribute('aria-expanded')==='false') await card.locator('#history-toggle').click();
    assert.match(await card.locator('.history-entry').innerText(),/Uppskattad kostnad.*3,00 SEK/);
    assert.match(await card.locator('.history-totals').innerText(),/kostnad ofullständig/);
    await card.locator('[data-main-tab="calendar"]').click();
    assert.equal(await card.locator('#calendar-time').inputValue(),'14:45');
    assert.equal(await card.locator('#calendar-summary').inputValue(),'Eget arbetspass');
    assert.equal(await card.locator('#repeat-frequency').inputValue(),'WEEKLY');
    await card.locator('#cancel-calendar').click();
    // Skip and a dated pause call the appropriate entities once.
    await card.locator('#more-actions').click();
    await card.locator('#skip-next').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.splice(0))),[{domain:'button',service:'press',data:{entity_id:'button.skip'}}]);
    await card.locator('#show-pause-date').click();
    await card.locator('#pause-until').fill('2027-03-28T02:30');
    await card.locator('#save-pause').click();
    assert.equal((await page.evaluate(()=>window.calls.length)),0,'A nonexistent local DST time must not start a pause');
    assert.match(await card.locator('.notice[role="alert"]').innerText(),/finns inte/);
    await card.locator('#pause-until').fill('2026-11-07T09:00');
    await card.locator('#save-pause').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.splice(0))),[
      {domain:'datetime',service:'set_value',data:{entity_id:'datetime.pause',datetime:'2026-11-07T09:00:00'}},
      {domain:'switch',service:'turn_on',data:{entity_id:'switch.paused'}}
    ]);
    await page.evaluate(()=>{window.hass.states['sensor.status'].attributes.automation_paused=true;window.hass.states['switch.paused'].state='on';document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await card.locator('.status').innerText(),/Pausad/);
    assert.match(await card.locator('#pause-automation').innerText(),/Återuppta/);
    await card.locator('#pause-automation').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.splice(0))),[{domain:'switch',service:'turn_off',data:{entity_id:'switch.paused'}}]);
    // Disabling weather must immediately discard the old forecast projection,
    // even if the ordinary schedule itself did not change.
    await page.evaluate(()=>{window.hass.states['sensor.status'].attributes.weather_enabled=false;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await todayEvent.count(),0,'Disabling forecast must use the underlying current-temperature schedule');
    assert.doesNotMatch(await card.locator('.calendar').innerText(),/Prognos/);
    // A late response from a forecast request must not re-enable it after the
    // user disabled the setting while that request was still pending.
    await page.evaluate(()=>{window.deferForecast=true;window.hass.states['sensor.status'].attributes.weather_enabled=true;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await page.evaluate(()=>window.pendingForecast.length),1);
    await page.evaluate(()=>{window.hass.states['sensor.status'].attributes.weather_enabled=false;document.querySelector('motorvarmare-card').hass={...window.hass};window.pendingForecast.pop()({events:[{departure:'2026-11-05T12:00:00Z',start:'2026-11-05T09:30:00Z',source:'Kalender',temperature_source:'forecast'}]});});
    await page.waitForTimeout(10);
    assert.equal(await todayEvent.count(),0,'A late forecast response must not resurrect a disabled forecast');
    assert.deepEqual(errors,[]);
    console.log('PASS: forecast, cost, tabs, unsaved drafts, skip, pause and mobile scroll');
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exit(1)});
