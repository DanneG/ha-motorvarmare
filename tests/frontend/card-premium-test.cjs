/* Exercise real card states, not the particular visual treatment. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:320,height:720},isMobile:true,hasTouch:true});
    const errors=[];
    page.on('pageerror', error=>errors.push(error.message));
    await page.clock.setFixedTime(new Date('2026-11-05T09:30:00Z'));
    await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><motorvarmare-card></motorvarmare-card></body></html>');
    await page.addStyleTag({content:'html,body{margin:0}motorvarmare-card,ha-card{display:block}motorvarmare-card{margin:8px}'});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{});
      customElements.define('ha-icon',class extends HTMLElement{});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.heater',calendar:'calendar.car',start_now:'button.start',stop_now:'button.stop',skip_next:'button.skip',automation_paused:'switch.pause',pause_until:'datetime.pause',manual_departure:'datetime.manual',clear_departure:'button.clear',weekly_times:[],weekly_enabled:[]};
      const attributes={friendly_name:'Bil status',control_entities:controls,temperature:-5,current_duration_minutes:90,schedule_7_days:[],heating_history:[],power_sensor_configured:true,energy_sensor_configured:true,power_w:500,energy_sensor_available:true,energy_monitor_status:'ok',alarm_active:false};
      const states={
        'sensor.status':{entity_id:'sensor.status',state:'idle',attributes},
        'switch.heater':{state:'off',attributes:{}},'calendar.car':{state:'off',attributes:{}},
        'button.start':{state:'unknown',attributes:{}},'button.stop':{state:'unknown',attributes:{}},
        'button.skip':{state:'unknown',attributes:{}},'switch.pause':{state:'off',attributes:{}},
        'datetime.pause':{state:'unknown',attributes:{}},'datetime.manual':{state:'unknown',attributes:{}},
        'button.clear':{state:'unknown',attributes:{}}
      };
      window.calls=[];
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},
        async callService(domain,service,data){window.calls.push({domain,service,data});},
        async callWS(){return {events:[],calendar_error:false};}};
      const card=document.querySelector('motorvarmare-card');card.setConfig({status_entity:'sensor.status'});card.hass=window.hass;
      window.update=(changes={}, state='waiting_to_start', switchState='off')=>{
        Object.assign(states['sensor.status'].attributes,changes);states['sensor.status'].state=state;
        states['switch.heater'].state=switchState;card.hass={...window.hass};
      };
    });
    const card=page.locator('motorvarmare-card');
    const timeline=card.locator('.departure-timeline');
    const start=card.locator('[data-timeline-start]');
    const departure=card.locator('[data-timeline-departure]');
    const stop=card.locator('[data-timeline-stop]');

    // No departure is not an invented time, and the empty calendar remains actionable.
    assert.equal(await timeline.count(),0,'No planned departure must produce no timeline');
    assert.equal(await card.locator('#empty-add-departure').isVisible(),true);
    await card.locator('#empty-add-departure').click();
    assert.equal(await card.locator('#calendar-time').isVisible(),true,'The empty state must open a real departure editor');
    await card.locator('#calendar-time').fill('14:15');
    await card.locator('#add-calendar').click();
    const created=await page.evaluate(()=>window.calls.shift());
    assert.equal(created.domain,'calendar');assert.equal(created.service,'create_event');
    assert.equal(created.data.entity_id,'calendar.car');assert.match(created.data.start_date_time,/T14:15/);

    // Show only genuinely available start/departure/stop times for a matched trip.
    const event={departure:'2026-11-05T13:00:00+01:00',start:'2026-11-05T11:30:00+01:00',end:'2026-11-05T13:30:00+01:00',source:'Planerad',duration_minutes:90,uid:'work',removable:true};
    await page.evaluate(event=>window.update({next_departure:event.departure,planned_start:event.start,schedule_7_days:[event],post_departure_minutes:30}),event);
    assert.match(await start.innerText(),/11:30/);assert.match(await departure.innerText(),/13:00/);assert.match(await stop.innerText(),/13:30/);
    await page.evaluate(()=>window.update({schedule_7_days:[]}));
    assert.equal(await stop.count(),0,'A missing schedule entry must not fabricate a stop time');
    // During the autumn clock change, 02:50 at UTC+2 really is before
    // 02:10 at UTC+1. Both offsets must be visible even without a stop time.
    await page.evaluate(()=>window.update({next_departure:'2027-10-31T02:10:00+01:00',planned_start:'2027-10-31T02:50:00+02:00',schedule_7_days:[]}));
    assert.equal(await stop.count(),0);
    assert.match(await start.innerText(),/02:50[\s\S]*(?:GMT|UTC)\+0?2\b/);
    assert.match(await departure.innerText(),/02:10[\s\S]*(?:GMT|UTC)\+0?1\b/);
    // A stop after the repeated hour must not hide the ambiguity between the
    // first 02:50 start and second 02:10 departure, in either presentation.
    await page.clock.setFixedTime(new Date('2027-10-30T09:30:00Z'));
    const dstEvent={start:'2027-10-31T02:50:00+02:00',departure:'2027-10-31T02:10:00+01:00',end:'2027-10-31T03:10:00+01:00',source:'Planerad',duration_minutes:80};
    await page.evaluate(event=>window.update({next_departure:event.departure,planned_start:event.start,schedule_7_days:[event]}),dstEvent);
    // The previously pinned date is now older than the 31-day archive.
    assert.equal(await card.locator('[data-mobile-day][aria-pressed="true"]').getAttribute('data-mobile-day'),'2027-10-30','An expired selection must return to today');
    assert.match(await start.innerText(),/02:50[\s\S]*(?:GMT|UTC)\+0?2\b/);
    assert.match(await departure.innerText(),/02:10[\s\S]*(?:GMT|UTC)\+0?1\b/);
    assert.match(await stop.innerText(),/03:10[\s\S]*(?:GMT|UTC)\+0?1\b/);
    await card.locator('[data-mobile-day="2027-10-31"]').click();
    const dstCalendar=await card.locator('.mobile-events').innerText();
    assert.match(dstCalendar,/02:50[\s\S]*(?:GMT|UTC)\+0?2\b/);
    assert.match(dstCalendar,/02:10[\s\S]*(?:GMT|UTC)\+0?1\b/);
    assert.match(dstCalendar,/03:10[\s\S]*(?:GMT|UTC)\+0?1\b/);
    await card.getByRole('button',{name:'Till i dag',exact:true}).click();
    await page.clock.setFixedTime(new Date('2026-11-05T09:30:00Z'));
    await page.evaluate(event=>window.update({next_departure:event.departure,planned_start:event.start,schedule_7_days:[{...event,suppressed:true}]}),event);
    assert.equal(await stop.count(),0,'A skipped trip must not present a scheduled heating stop');
    await page.evaluate(event=>window.update({skipped_departure:event.departure}),event);
    assert.equal(await timeline.count(),0,'A skipped departure must not show a heating timeline');

    // A pause is immediately visible; active heating uses its actual end,
    // rather than presenting an unrelated scheduled trip as a running session.
    await page.evaluate(event=>{window.hass.states['switch.pause'].state='on';window.update({schedule_7_days:[event],skipped_departure:null,automation_paused:true});},event);
    assert.match(await card.locator('.wrap').innerText(),/Pausad/);
    assert.equal(await card.locator('#pause-automation').isVisible(),true);
    assert.equal(await timeline.count(),0,'Paused automation must not show an active scheduled timeline');
    await page.evaluate(()=>{window.hass.states['switch.pause'].state='off';window.update({automation_paused:false,owned:true,active_until:'2026-11-05T12:45:00+01:00'},'heating','on');});
    assert.equal(await timeline.count(),0,'An active session must not be confused with a future departure');
    assert.match(await card.locator('.active-milestones').innerText(),/12:45/);
    assert.equal(await card.locator('#stop-now').isVisible(),true);

    // Midnight-crossing heating appears on both selected local calendar days.
    const overnight={departure:'2026-11-06T00:20:00+01:00',start:'2026-11-05T23:40:00+01:00',end:'2026-11-06T00:20:00+01:00',source:'Planerad',duration_minutes:40,uid:'night',removable:true};
    await page.evaluate(event=>window.update({owned:false,active_until:null,next_departure:event.departure,planned_start:event.start,schedule_7_days:[event],post_departure_minutes:0},'waiting_to_start','off'),overnight);
    await card.locator('[data-mobile-day="2026-11-05"]').click();
    assert.match(await card.locator('.mobile-events').innerText(),/23:40/);
    await card.locator('[data-mobile-day="2026-11-06"]').click();
    assert.match(await card.locator('.mobile-events').innerText(),/00:20/);

    // The cable warning is available regardless of the chosen view.
    await page.evaluate(()=>window.update({alarm_active:true,energy_monitor_status:'low_power',power_w:0},'heating','on'));
    for (const view of ['calendar','energy','settings']) {
      await card.locator(`[data-main-tab="${view}"]`).click();
      assert.equal(await card.locator('.power-alarm').isVisible(),true,`Cable warning must remain visible in ${view}`);
    }

    // Both theme palettes and a 320px device retain usable, named controls and fit.
    for (const theme of [
      {'--primary-text-color':'#17232d','--secondary-text-color':'#53636e','--card-background-color':'#fff','--secondary-background-color':'#edf2f6','--divider-color':'#d4dce2','--primary-color':'#007f95','--text-primary-color':'#fff'},
      {'--primary-text-color':'#f2f4f5','--secondary-text-color':'#a7b1ba','--card-background-color':'#1c2024','--secondary-background-color':'#293038','--divider-color':'#3d464e','--primary-color':'#46c7dc','--text-primary-color':'#09282d'}
    ]) {
      await card.evaluate((el,vars)=>Object.entries(vars).forEach(([key,value])=>el.style.setProperty(key,value)),theme);
      for (const view of ['calendar','energy','settings']) {
        await card.locator(`[data-main-tab="${view}"]`).click();
        assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),`${view} must fit at 320px`);
        assert.equal(await card.locator('.power-alarm').isVisible(),true);
      }
    }
    // Home Assistant may retain old attributes when the status entity becomes
    // unavailable. Those values cannot be presented as current measurements.
    await page.evaluate(()=>window.update({next_departure:'2027-10-31T02:10:00+01:00',planned_start:'2027-10-31T02:50:00+02:00',temperature:42.3,power_w:9876,session_energy_kwh:87.654,energy_session_status:'measuring',alarm_active:false,schedule_7_days:[{departure:'2026-11-05T13:00:00+01:00',start:'2026-11-05T11:30:00+01:00',end:'2026-11-05T13:30:00+01:00',source:'Planerad'}]},'unavailable','off'));
    assert.equal(await timeline.count(),0,'Unavailable status cannot support a current departure timeline');
    assert.doesNotMatch(await card.locator('.departure-summary').innerText(),/02:10|42,3/,'Retained departure and temperature must not be presented as current');
    await card.locator('[data-main-tab="energy"]').click();
    const energyText=await card.locator('[data-main-panel="energy"]').innerText();
    assert.doesNotMatch(energyText,/9[\s\u00a0\u202f]*876|87,654/,'Retained power and session energy must not be presented as live values');
    await card.locator('[data-main-tab="calendar"]').click();
    assert.equal(await card.locator('.mobile-event').count(),0,'Unavailable status must not present stale departures as current');
    assert.deepEqual(errors,[]);
    console.log('PASS: empty state, truthful timeline, pause, overnight calendar, alerts and 320px themes');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
