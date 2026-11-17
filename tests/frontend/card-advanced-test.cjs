/* Run with Playwright on NODE_PATH and Chrome installed. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page=await browser.newPage({viewport:{width:440,height:1000}});
    await page.clock.setFixedTime(new Date('2026-11-05T09:30:50Z'));
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:'body{background:#1c1c1c;color:#eee}motorvarmare-card{display:block;width:400px;background:#1c1c1c;--primary-text-color:#eee;--secondary-text-color:#aaa;--card-background-color:#111;--secondary-background-color:#333;--divider-color:#555;--primary-color:#00a6ce;--text-primary-color:#fff}'});
    await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{});});
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={manual_departure:'datetime.car',clear_departure:'button.clear',heater_switch:'switch.heater',calendar:'calendar.car',start_now:'button.start',stop_now:'button.stop',weekly_times:[],weekly_enabled:[]};
      const states={'sensor.status':{entity_id:'sensor.status',state:'waiting',attributes:{friendly_name:'Bil status',control_entities:controls,temperature:-4,current_duration_minutes:36,schedule_query_supported:true,schedule_7_days:[],heating_history:[],history_energy_totals:{daily:[{period_start:'2026-11-05',energy_kwh:1.25,incomplete:false},{period_start:'2026-11-04',energy_kwh:null,incomplete:true}],weekly:[{period_start:'2026-11-02',energy_kwh:2.5,incomplete:true}],monthly:[{period_start:'2026-11-01',energy_kwh:3.75,incomplete:false}],has_older:{daily:false,weekly:false,monthly:false}}}},'switch.heater':{state:'off',attributes:{}},'calendar.car':{state:'off',attributes:{}},'button.start':{state:'unknown',attributes:{}},'button.stop':{state:'unknown',attributes:{}},'button.clear':{state:'unknown',attributes:{}},'datetime.car':{state:'unknown',attributes:{}}};
      window.calls=[];window.pending=[];window.deferSchedule=false;window.serverEvents=[];
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(domain,service,data){window.calls.push({domain,service,data});},callWS(message){window.calls.push({ws:message});if(message.type==='motorvarmare/get_schedule'){if(window.deferSchedule)return new Promise((resolve,reject)=>window.pending.push({resolve,reject}));return Promise.resolve({events:window.serverEvents,calendar_error:false});}if(message.type==='calendar/event/create')window.serverEvents=[{departure:message.event.dtstart,start:'2026-11-06T07:24:00.000Z',source:'Planerad',uid:'new',recurrence_id:message.event.dtstart,removable:true}];if(message.type==='calendar/event/delete')window.serverEvents=[];return Promise.resolve();}};
      const card=document.createElement('motorvarmare-card');card.setConfig({status_entity:'sensor.status'});card.hass=window.hass;document.body.appendChild(card);
    });
    const card=page.locator('motorvarmare-card');
    // The current local time is used for today's new departure, rounded up.
    await card.locator('.mobile-add').click();
    assert.equal(await card.locator('#calendar-time').inputValue(),'10:31');
    // A delayed schedule response must never steal focus or discard an unsaved value.
    await card.locator('#calendar-time').fill('10:45');
    await page.evaluate(()=>{window.deferSchedule=true;document.querySelector('motorvarmare-card')._loadCalendarWindow(true);});
    await page.evaluate(()=>window.pending.pop().resolve({events:[],calendar_error:false}));
    await page.waitForTimeout(20);
    assert.equal(await page.evaluate(()=>document.querySelector('motorvarmare-card').shadowRoot.activeElement.id),'calendar-time');
    assert.equal(await card.locator('#calendar-time').inputValue(),'10:45');
    await card.locator('#calendar-time').blur();await page.waitForTimeout(20);
    assert.equal(await card.locator('#calendar-time').inputValue(),'10:45');
    await page.evaluate(()=>{window.deferSchedule=false;window.calls=[];});
    await card.locator('#cancel-calendar').click();
    const keys=await page.evaluate(()=>document.querySelector('motorvarmare-card')._dayKeys());
    await card.locator(`[data-mobile-day="${keys[1]}"]`).click();
    await card.locator('.mobile-add').click();
    await card.locator('#calendar-time').fill('09:00');
    await card.locator('#repeat-frequency').selectOption('WEEKLY');
    await card.locator('[data-repeat-day="MO"]').check();
    await card.locator('[data-repeat-day="TU"]').check();await card.locator('[data-repeat-day="WE"]').check();await card.locator('[data-repeat-day="TH"]').check();
    await card.locator('#repeat-until').fill('2026-12-31');
    if (process.env.MOTORVARMARE_SCREENSHOTS) await card.locator('#repeat-until').blur();
    if (process.env.MOTORVARMARE_SCREENSHOTS) await card.locator('.cal-editor').screenshot({path:path.join(process.env.MOTORVARMARE_SCREENSHOTS,'schedule.png')});
    await card.locator('#add-calendar').click();
    const create=await page.evaluate(()=>window.calls.shift());
    assert.equal(create.ws.type,'calendar/event/create');
    assert.equal(create.ws.event.dtstart,'2026-11-06T08:00:00.000Z');
    assert.match(create.ws.event.rrule,/FREQ=WEEKLY;INTERVAL=1;BYDAY=.*MO.*FR/);
    assert.match(create.ws.event.rrule,/UNTIL=20261231T225959Z/);
    await page.waitForFunction(()=>document.querySelector('motorvarmare-card').shadowRoot.querySelector('[data-mobile-departure="2026-11-06T08:00:00.000Z"]'));
    await page.evaluate(()=>{window.calls=[];window.deferSchedule=true;});
    const conversions=await page.evaluate(()=>{const c=document.querySelector('motorvarmare-card');return [c._localToUtc('2027-07-31T23:59'),c._localToUtc('2027-12-31T23:59'),c._localToUtc('2027-03-28T02:30')];});
    assert.deepEqual(conversions,['2027-07-31T21:59:00.000Z','2027-12-31T22:59:00.000Z',null]);
    // Rapid forward navigation: stale replies cannot overwrite the latest week.
    await card.locator('#window-next').click();
    await card.locator('#window-next').click();
    const requests=await page.evaluate(()=>window.calls.filter(c=>c.ws?.type==='motorvarmare/get_schedule').map(c=>c.ws));
    assert.equal(requests.length,2);assert.equal(requests[0].start,'2026-11-12');assert.equal(requests[1].start,'2026-11-19');
    await page.evaluate(()=>window.pending[1].resolve({events:[{departure:'2026-11-20T09:00:00Z',start:'2026-11-20T08:24:00Z',source:'Kalender'}],calendar_error:true}));
    await page.waitForFunction(()=>document.querySelector('motorvarmare-card').shadowRoot.textContent.includes('vissa avresor kan saknas'));
    await page.evaluate(()=>window.pending[0].resolve({events:[{departure:'2026-11-13T09:00:00Z',start:'2026-11-13T08:24:00Z',source:'Planerad'}],calendar_error:false}));
    await page.waitForTimeout(20);
    assert.equal(await card.locator('[data-mobile-departure="2026-11-13T09:00:00Z"]').count(),0);
    assert.equal(await card.locator('[data-mobile-departure="2026-11-20T09:00:00Z"]').count(),1);
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.current_duration_minutes=60;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await card.locator('[data-mobile-departure="2026-11-20T09:00:00Z"]').innerText(),/Värmer 09:00–10:00[\s\S]*Avresa 10:00/);
    // A temperature stop blocks automatic scheduling even while Start now remains available.
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.temperature=9.9;a.temperature_blocked=true;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await card.locator('[data-mobile-departure="2026-11-20T09:00:00Z"].marker-event').count(),1);
    assert.doesNotMatch(await card.locator('[data-mobile-departure="2026-11-20T09:00:00Z"]').innerText(),/Värmer 09:00/);
    assert.equal(await card.locator('#start-now').isEnabled(),true);
    await card.locator('#start-now').click();
    assert.ok(await page.evaluate(()=>window.calls.some(c=>c.domain==='button' && c.service==='press' && c.data.entity_id==='button.start')));
    // The future estimate reappears as soon as the backend releases the block.
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.temperature=9.5;a.temperature_blocked=false;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await card.locator('[data-mobile-departure="2026-11-20T09:00:00Z"]').innerText(),/Värmer 09:00–10:00[\s\S]*Avresa 10:00/);
    // An optional post-departure period changes the actual stop, not the departure.
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.post_departure_minutes=30;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await card.locator('[data-mobile-departure="2026-11-20T09:00:00Z"]').innerText(),/Värmer 09:00–10:30[\s\S]*Avresa 10:00/);
    assert.match(await card.locator('.summary-metrics').innerText(),/Värmetid\s*1 tim/);
    assert.match(await card.locator('.summary-metrics').innerText(),/Efter avresa\s*30 min/);
    // Overlap must include the extra 30 minutes after the first departure.
    await page.evaluate(()=>{const c=document.querySelector('motorvarmare-card');c._windowEvents.push({departure:'2026-11-20T10:15:00Z',source:'Kalender'});c.hass={...window.hass};});
    assert.match(await card.locator('.calendar-subtitle').innerText(),/Överlappande tider/);
    // Render intervals crossing both the beginning and end of the displayed week.
    await page.evaluate(()=>{const c=document.querySelector('motorvarmare-card');c._windowEvents=[{departure:'2026-11-18T22:45:00Z',source:'Planerad',uid:'overnight',removable:true},{departure:'2026-11-25T22:45:00Z',source:'Planerad'}];c.hass={...window.hass};});
    assert.equal(await card.locator('[data-departure="2026-11-18T22:45:00Z"][data-segment-day="2026-11-19"].heating-event').count(),1);
    assert.equal(await card.locator('[data-departure="2026-11-25T22:45:00Z"][data-segment-day="2026-11-25"].heating-event').count(),1);
    await card.locator('[data-mobile-day="2026-11-19"]').click();
    await card.locator('[data-mobile-departure="2026-11-18T22:45:00Z"] [data-edit-index]').click();
    assert.equal(await card.locator('#calendar-date').inputValue(),'2026-11-18');
    await card.locator('#cancel-calendar').click();
    // Turning the setting off removes the next-day portion and restores the old stop time.
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.post_departure_minutes=0;document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await card.locator('[data-departure="2026-11-18T22:45:00Z"][data-segment-day="2026-11-19"]').count(),0);
    assert.doesNotMatch(await card.locator('.summary-metrics').innerText(),/Efter avresa/);
    await card.locator('#window-today').click();
    // Today's view uses the integration's projected end, without shifting departure.
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.post_departure_minutes=30;a.schedule_7_days=[{departure:'2026-11-06T08:00:00Z',start:'2026-11-06T07:00:00Z',end:'2026-11-06T08:30:00Z',source:'Planerad'}];document.querySelector('motorvarmare-card').hass={...window.hass};});
    await card.locator(`[data-mobile-day="${keys[1]}"]`).click();
    assert.match(await card.locator('[data-mobile-departure="2026-11-06T08:00:00Z"]').innerText(),/Värmer 08:00–09:30[\s\S]*Avresa 09:00/);
    await page.evaluate(()=>{window.hass.states['sensor.status'].attributes.post_departure_minutes=0;});
    await page.evaluate(()=>{const a=window.hass.states['sensor.status'].attributes;a.schedule_7_days=[{departure:'2026-11-06T08:00:00Z',start:'2026-11-06T07:24:00Z',source:'Planerad',uid:'series',recurrence_id:'2026-11-06T08:00:00+00:00',removable:true}];document.querySelector('motorvarmare-card').hass={...window.hass};window.calls=[];window.deferSchedule=false;window.serverEvents=a.schedule_7_days;});
    await card.locator(`[data-mobile-day="${keys[1]}"]`).click();
    // Editing one occurrence uses the series UID and original recurrence ID atomically.
    await card.locator('[data-edit-index]').filter({visible:true}).first().click();
    await card.locator('#edit-one').click();
    await card.locator('#calendar-time').fill('10:00');
    await card.locator('#add-calendar').click();
    let update=(await page.evaluate(()=>window.calls.shift())).ws;
    assert.equal(update.type,'calendar/event/update');assert.equal(update.uid,'series');
    assert.equal(update.recurrence_id,'2026-11-06T08:00:00+00:00');
    assert.equal(update.event.dtstart,'2026-11-06T09:00:00.000Z');assert.equal(update.event.rrule,undefined);
    await page.waitForFunction(()=>!document.querySelector('motorvarmare-card')._windowLoading);
    await page.evaluate(async()=>{window.serverEvents=[{departure:'2026-11-06T08:00:00Z',start:'2026-11-06T07:24:00Z',source:'Planerad',uid:'series',recurrence_id:'2026-11-06T08:00:00+00:00',series_start:'2026-10-30T09:00:00Z',rrule:'FREQ=WEEKLY;BYDAY=FR',summary:'Ändrad förekomst',series_summary:'Avresa',exceptions_count:1,removable:true}];await document.querySelector('motorvarmare-card')._loadCalendarWindow(true);window.calls=[];});
    await card.locator('[data-edit-index]').filter({visible:true}).first().click();await card.locator('#edit-series').click();
    assert.equal(await card.locator('#calendar-date').inputValue(),'2026-10-30');
    assert.equal(await card.locator('#calendar-summary').inputValue(),'Avresa');
    await card.locator('#calendar-summary').fill('Arbete');await card.locator('#add-calendar').click();
    assert.match(await page.evaluate(()=>document.querySelector("motorvarmare-card").shadowRoot.textContent),/Bekräfta informationen/);
    assert.equal(await page.evaluate(()=>window.calls.length),0);
    await card.locator('#confirm-series-change').check();await card.locator('#add-calendar').click();
    update=(await page.evaluate(()=>window.calls.shift())).ws;
    assert.equal(update.type,'calendar/event/update');assert.equal(update.uid,'series');assert.equal(update.recurrence_id,undefined);
    assert.equal(update.event.summary,'Arbete');assert.equal(update.event.dtstart,'2026-10-30T09:00:00.000Z');
    assert.equal(update.event.rrule,'FREQ=WEEKLY;BYDAY=FR');
    await page.waitForFunction(()=>!document.querySelector('motorvarmare-card')._windowLoading);
    // A rule change is explicit, keeps the UID, and warns before existing exceptions are cleared.
    await page.evaluate(()=>{window.calls=[];});
    await card.locator('[data-edit-index]').filter({visible:true}).first().click();await card.locator('#edit-series').click();
    assert.match(await card.locator('.series-warning').innerText(),/undantag/);
    await card.locator('#repeat-interval').fill('2');
    await card.locator('#confirm-series-change').check();await card.locator('#add-calendar').click();
    update=(await page.evaluate(()=>window.calls.shift())).ws;
    assert.equal(update.type,'calendar/event/update');assert.equal(update.uid,'series');assert.equal(update.recurrence_id,undefined);
    assert.match(update.event.rrule,/FREQ=WEEKLY;INTERVAL=2;BYDAY=FR/);
    await page.waitForFunction(()=>!document.querySelector('motorvarmare-card')._windowLoading);
    await page.evaluate(()=>{window.calls=[];});
    await card.locator('.mobile-remove').click();
    assert.match(await card.locator('.cal-editor').innerText(),/hela serien/i);
    await card.locator('#delete-one').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.shift())).ws,{type:'calendar/event/delete',entity_id:'calendar.car',uid:'series',recurrence_id:'2026-11-06T08:00:00+00:00'});
    await page.waitForFunction(()=>!document.querySelector('motorvarmare-card').shadowRoot.querySelector('.mobile-remove'));
    await page.evaluate(async()=>{window.calls=[];window.serverEvents=window.hass.states['sensor.status'].attributes.schedule_7_days;await document.querySelector('motorvarmare-card')._loadCalendarWindow(true);window.calls=[];});
    await card.locator('.mobile-remove').click();await card.locator('#delete-series').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.shift())).ws,{type:'calendar/event/delete',entity_id:'calendar.car',uid:'series'});
    // Aggregates distinguish missing measurements and incomplete periods.
    await card.locator('[data-main-tab="energy"]').click();
    if (await card.locator('#history-toggle').getAttribute('aria-expanded')==='false') await card.locator('#history-toggle').click();
    assert.match(await card.locator('.history-totals').innerText(),/1,25 kWh/);
    if (process.env.MOTORVARMARE_SCREENSHOTS) await card.locator('.history-totals').screenshot({path:path.join(process.env.MOTORVARMARE_SCREENSHOTS,'history.png')});
    assert.match(await card.locator('.history-totals').innerText(),/Inget mätvärde.*ofullständigt/s);
    await card.locator('[data-total-period="weekly"]').click();
    assert.match(await card.locator('.history-totals').innerText(),/2,50 kWh.*ofullständigt/s);
    await card.locator('[data-total-period="monthly"]').click();
    assert.match(await card.locator('.history-totals').innerText(),/3,75 kWh/);
    // Old installations still render and explain that a future view needs an integration update.
    await card.locator('[data-main-tab="calendar"]').click();
    await page.evaluate(()=>{window.hass.states['sensor.status'].attributes.schedule_query_supported=false;document.querySelector('motorvarmare-card').hass={...window.hass};});
    await card.locator('#window-next').click();
    assert.match(await page.evaluate(()=>document.querySelector("motorvarmare-card").shadowRoot.textContent),/Uppdatera integrationen för att visa kalendern/);
    // A departure created at 23:59 never wraps back to 00:00 on the same day.
    await page.clock.setFixedTime(new Date('2026-11-05T22:59:30Z'));
    assert.equal(await page.evaluate(()=>document.querySelector('motorvarmare-card')._defaultCalendarTime('2026-11-05')),'23:59');
    assert.deepEqual(errors,[]);
    console.log('PASS: forward calendar, stale requests, current time, recurring rules, local timezone and energy totals');
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});

