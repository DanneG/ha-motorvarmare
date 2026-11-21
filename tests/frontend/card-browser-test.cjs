/* Run with Playwright available on NODE_PATH and Chrome installed. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({ headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
  try {
    const page = await browser.newPage();
    // Keep the calendar dates and Stockholm UTC offset deterministic year-round.
    await page.clock.setFixedTime(new Date('2026-11-05T12:00:00Z'));
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.setViewportSize({width:1360,height:1400});
    await page.addStyleTag({content:`body{margin:0;background:#f1f5f8;padding:24px;font-family:Roboto,Arial,sans-serif} motorvarmare-card{--primary-text-color:#162f3c;--secondary-text-color:#5b7180;--card-background-color:#fff;--secondary-background-color:#eef4f6;--divider-color:#dce6eb;--primary-color:#087c99;--text-primary-color:#fff;display:block;max-width:1120px;margin:auto}`});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{connectedCallback(){Object.assign(this.style,{display:'block',background:'var(--card-background-color)',borderRadius:'15px',boxShadow:'0 3px 20px #173a4c1a'});}});
      customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent='🚗';}});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(() => {
      const controls = {
        manual_departure:'datetime.car_manual', clear_departure:'button.car_clear', heater_switch:'switch.car_heater',
        calendar:'calendar.car_schedule', start_now:'button.car_start', stop_now:'button.car_stop',
        weekly_times:Array.from({length:7}, (_,i)=>`time.car_${i}`), weekly_enabled:Array.from({length:7}, (_,i)=>`switch.car_${i}`),
      };
      const states = {
        'sensor.car_status':{entity_id:'sensor.car_status', state:'waiting_to_start',attributes:{friendly_name:'Car Status',control_entities:controls,temperature:-4,current_duration_minutes:36,owned:false,schedule_7_days:[]}},
        'datetime.car_manual':{entity_id:'datetime.car_manual',state:'unknown',attributes:{}},
        'button.car_clear':{entity_id:'button.car_clear',state:'unknown',attributes:{}},
        'button.car_start':{entity_id:'button.car_start',state:'unknown',attributes:{}},
        'button.car_stop':{entity_id:'button.car_stop',state:'unknown',attributes:{}},
        'calendar.car_schedule':{entity_id:'calendar.car_schedule',state:'off',attributes:{}},
        'switch.car_heater':{entity_id:'switch.car_heater',state:'off',attributes:{}},
      };
      controls.weekly_times.forEach(id=>states[id]={entity_id:id,state:'07:00:00',attributes:{}});
      controls.weekly_enabled.forEach(id=>states[id]={entity_id:id,state:'off',attributes:{}});
      window.calls=[];
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},
        async callService(domain,service,data){ window.calls.push({domain,service,data}); },
        async callWS(data){ window.calls.push({ws:data}); }};
      const card=document.createElement('motorvarmare-card');
      card.setConfig({status_entity:'sensor.car_status',title:'Bil 1'});
      card.hass=window.hass;
      const tomorrow=card._dayKeys()[1], fourth=card._dayKeys()[3], fifth=card._dayKeys()[4];
      states['sensor.car_status'].attributes.schedule_7_days=[
        {departure:`${tomorrow}T09:30:00Z`,start:`${tomorrow}T08:54:00Z`,source:'Planerad',uid:'one',removable:true,duration_minutes:36},
        {departure:`${tomorrow}T12:30:00Z`,start:`${tomorrow}T11:54:00Z`,source:'Kalender',duration_minutes:36},
        {departure:`${fourth}T06:30:00Z`,start:`${fourth}T05:54:00Z`,source:'Veckoschema',duration_minutes:36},
        {departure:`${fifth}T07:00:00Z`,start:`${fifth}T06:24:00Z`,source:'Planerad',uid:'two',removable:true,duration_minutes:36},
      ];
      const attrs=states['sensor.car_status'].attributes;
      attrs.next_departure=attrs.schedule_7_days[0].departure; attrs.planned_start=attrs.schedule_7_days[0].start; attrs.duration_minutes=36; attrs.source='Planerad';
      card.hass=window.hass;
      document.body.appendChild(card);
    });
    const card=page.locator('motorvarmare-card');
    assert.match(await card.locator('.wrap').innerText(),/Väntar på start/);
    assert.match(await card.locator('.wrap').innerText(),/Värmer i 36 min/);
    assert.equal(await card.locator('.cal-day').count(),7);
    assert.equal(await card.locator('.cal-event').count(),4);
    assert.ok(await card.locator('[data-remove-uid]').count() >= 2,'Local departures remain individually removable');
    assert.ok(await card.locator('.cal-scroll').evaluate(el=>el.scrollTop) > 0,'Calendar initially shows the relevant hours even when configured before attachment');
    if (process.env.MOTORVARMARE_PREVIEW_DARK === '1') await page.addStyleTag({content:`body{background:#1a1b1c} motorvarmare-card{--primary-text-color:#e8eaed;--secondary-text-color:#b8c0cb;--card-background-color:#101113;--secondary-background-color:#292a2d;--divider-color:#3c4043;--primary-color:#a8c7fa;--text-primary-color:#062e6f}`});
    if (process.env.MOTORVARMARE_PREVIEW_PATH) await page.screenshot({path:process.env.MOTORVARMARE_PREVIEW_PATH,fullPage:true});
    await card.locator('#start-now').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.shift())),{domain:'button',service:'press',data:{entity_id:'button.car_start'}});
    await page.evaluate(()=>{window.hass.states['sensor.car_status'].attributes.owned=true;window.hass.states['switch.car_heater'].state='on';document.querySelector('motorvarmare-card').hass={...window.hass};});
    await card.locator('#stop-now').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.shift())),{domain:'button',service:'press',data:{entity_id:'button.car_stop'}});
    const tomorrow=await page.evaluate(()=>document.querySelector('motorvarmare-card')._dayKeys()[1]);
    await card.locator(`[data-grid-day="${tomorrow}"]`).click({position:{x:8,y:18.5*64}});
    assert.equal(await card.locator('#calendar-time').inputValue(),'18:30','Clicking an empty slot selects its time');
    await card.locator('#cancel-calendar').click();
    await card.locator('.cal-agenda summary').click();
    await card.locator('.cal-scroll').evaluate(el=>{el.scrollTop=700;});
    const scrollBefore=await card.locator('.cal-scroll').evaluate(el=>el.scrollTop);
    await page.evaluate(()=>{document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await card.locator('.cal-scroll').evaluate(el=>el.scrollTop),scrollBefore,'Home Assistant updates must preserve the selected calendar position');
    assert.equal(await card.locator('.cal-agenda').evaluate(el=>el.open),true,'Home Assistant updates must preserve the open departures list');
    await card.locator(`.desktop-calendar [data-add-day="${tomorrow}"]`).click();
    await card.locator('#calendar-time').fill('11:15');
    await card.locator('#add-calendar').click();
    const add=await page.evaluate(()=>window.calls.shift());
    assert.deepEqual(add,{domain:'calendar',service:'create_event',data:{entity_id:'calendar.car_schedule',summary:'Avresa',start_date_time:`${tomorrow}T11:15:00`,end_date_time:`${tomorrow}T11:16:00`}});
    await card.locator(`.desktop-calendar [data-add-day="${tomorrow}"]`).click();
    await card.locator('#calendar-time').fill('14:30');
    await card.locator('#add-calendar').click();
    const second=await page.evaluate(()=>window.calls.shift());
    assert.equal(second.data.start_date_time,`${tomorrow}T14:30:00`);
    assert.equal(second.data.end_date_time,`${tomorrow}T14:31:00`);
    await card.locator('.desktop-calendar [data-remove-uid="one"]').first().click();
    await card.locator('#commit-removal').click();
    assert.deepEqual((await page.evaluate(()=>window.calls.shift())),{ws:{type:'calendar/event/delete',entity_id:'calendar.car_schedule',uid:'one'}});
    // Two simultaneous windows must remain independently visible. Intervals
    // crossing midnight must be drawn in both local-day columns, including a
    // departure just outside the visible week whose heating starts within it.
    const cases = await page.evaluate(() => {
      const element=document.querySelector('motorvarmare-card');
      const keys=element._dayKeys(), day=keys[1], next=keys[2], last=keys[6];
      const eighth=new Date(`${last}T12:00:00Z`); eighth.setUTCDate(eighth.getUTCDate()+1);
      const beyond=eighth.toISOString().slice(0,10);
      const crossEnd=`${next}T00:20:00+01:00`, midnightEnd=`${next}T00:00:00+01:00`, overlapEnd=`${day}T10:45:00+01:00`, beyondEnd=`${beyond}T00:20:00+01:00`;
      const attrs=window.hass.states['sensor.car_status'].attributes;
      attrs.schedule_7_days.push(
        {start:`${day}T23:40:00+01:00`,departure:crossEnd,source:'Planerad',uid:'cross',removable:true,duration_minutes:40},
        {start:`${day}T23:30:00+01:00`,departure:midnightEnd,source:'Planerad',uid:'midnight',removable:true,duration_minutes:30},
        {start:`${day}T10:20:00+01:00`,departure:overlapEnd,source:'Planerad',uid:'overlap',removable:true,duration_minutes:25},
        {start:`${last}T23:30:00+01:00`,departure:beyondEnd,source:'Veckoschema',duration_minutes:50},
        {start:`${day}T13:00:00+01:00`,departure:`${day}T13:30:00+01:00`,source:'Planerad',suppressed:true,duration_minutes:30},
        {start:null,departure:`${day}T14:00:00+01:00`,source:'Planerad',duration_minutes:0},
        {start:null,departure:`${day}T15:00:00+01:00`,source:'Planerad',duration_minutes:null}
      );
      element.hass={...window.hass};
      return {day,next,last,crossEnd,midnightEnd,overlapEnd,beyondEnd,original:`${day}T09:30:00Z`};
    });
    const cross=card.locator(`[data-departure="${cases.crossEnd}"]`);
    assert.equal(await cross.count(),2,'Cross-midnight heating must appear on both days');
    assert.equal(await card.locator(`[data-departure="${cases.crossEnd}"][data-segment-day="${cases.day}"]`).count(),1);
    assert.equal(await card.locator(`[data-departure="${cases.crossEnd}"][data-segment-day="${cases.next}"]`).count(),1);
    assert.equal(await card.locator(`[data-departure="${cases.midnightEnd}"][data-segment-day="${cases.day}"]`).count(),1);
    assert.equal(await card.locator(`[data-departure="${cases.midnightEnd}"][data-segment-day="${cases.next}"]`).count(),1,'Midnight departure remains visible and removable on the departure day');
    assert.equal(await card.locator(`[data-departure="${cases.beyondEnd}"][data-segment-day="${cases.last}"]`).count(),1);
    assert.equal(await card.locator('.desktop-calendar .marker-event').count(),4,'Stopped, zero/unknown heating and the midnight departure use markers');
    assert.match(await card.locator(`[data-departure="${cases.original}"]`).getAttribute('aria-label'),/09:54.*10:30/);
    const geometry=await page.evaluate(({original,overlapEnd,day})=>{
      const root=document.querySelector('motorvarmare-card').shadowRoot;
      const first=root.querySelector(`[data-departure="${original}"][data-segment-day="${day}"]`).getBoundingClientRect();
      const second=root.querySelector(`[data-departure="${overlapEnd}"][data-segment-day="${day}"]`).getBoundingClientRect();
      return {first:{left:first.left,right:first.right,top:first.top,bottom:first.bottom},second:{left:second.left,right:second.right,top:second.top,bottom:second.bottom}};
    },cases);
    assert.ok(geometry.first.top < geometry.second.bottom && geometry.second.top < geometry.first.bottom,'Overlapping intervals must overlap vertically');
    assert.ok(geometry.first.right <= geometry.second.left || geometry.second.right <= geometry.first.left,'Overlapping intervals must be placed in separate lanes');
    // The preceding interactions pinned tomorrow. Follow today again before
    // switching the fixture clock to the week of the autumn DST transition.
    await card.getByRole('button',{name:'Till i dag',exact:true}).click();
    await page.clock.setFixedTime(new Date('2026-10-24T12:00:00Z'));
    await page.evaluate(()=>{const a=window.hass.states['sensor.car_status'].attributes;a.schedule_7_days=[{start:'2026-10-25T02:50:00+02:00',departure:'2026-10-25T02:20:00+01:00',source:'Planerad',uid:'dst',removable:true,duration_minutes:30}];document.querySelector('motorvarmare-card').hass={...window.hass};});
    const fallback=card.locator('[data-departure="2026-10-25T02:20:00+01:00"]');
    assert.equal(await fallback.count(),1,'Repeated autumn hour must not disappear');
    assert.match(await fallback.getAttribute('aria-label'),/02:50.*GMT\+2.*02:20.*GMT\+1/,'Repeated hour must identify both UTC offsets');
    await page.clock.setFixedTime(new Date('2026-11-05T12:00:00Z'));
    await page.evaluate(({day})=>{const a=window.hass.states['sensor.car_status'].attributes;a.schedule_7_days=[
      {departure:`${day}T09:30:00Z`,start:`${day}T08:54:00Z`,source:'Planerad',uid:'one',removable:true,duration_minutes:36},
      {departure:`${day}T12:30:00Z`,start:`${day}T11:54:00Z`,source:'Kalender',duration_minutes:36},
      {departure:'2026-11-08T06:30:00Z',start:'2026-11-08T05:54:00Z',source:'Veckoschema',duration_minutes:36},
      {departure:'2026-11-09T07:00:00Z',start:'2026-11-09T06:24:00Z',source:'Planerad',uid:'two',removable:true,duration_minutes:36}];document.querySelector('motorvarmare-card').hass={...window.hass};},cases);
    await page.evaluate(()=>{window.hass.locale.language='en';window.hass.states['sensor.car_status'].attributes.error='Kunde inte stänga av brytaren; försöker igen; Kalendern kan inte läsas; se Home Assistants logg';document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await card.locator('.wrap').innerText(),/Next 7 days/);
    assert.match(await card.locator('.wrap').innerText(),/Waiting to start/);
    assert.match(await card.locator('.wrap').innerText(),/Scheduled/);
    assert.match(await card.locator('.wrap').innerText(),/Could not turn off the switch; retrying; Calendar could not be read/);
    assert.doesNotMatch(await card.locator('.wrap').innerText(),/Kommande 7 dagar/);
    await page.evaluate(()=>{const a=window.hass.states['sensor.car_status'].attributes;a.schedule_7_days[1].start=a.schedule_7_days[0].start;a.current_duration_minutes=0;a.owned=false;window.hass.states['switch.car_heater'].state='off';document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.doesNotMatch(await card.locator('.wrap').innerText(),/Overlapping times/);
    await card.locator('.schedule-details summary').click();
    assert.match(await card.locator('.wrap').innerText(),/Overlapping times/);
    assert.match(await card.locator('.wrap').innerText(),/formula gives no heating time/);
    assert.equal(await card.locator('#start-now').isDisabled(),true);
    await page.setViewportSize({width:320,height:1000});
    const fits=await card.evaluate(el=>el.scrollWidth<=el.clientWidth);
    assert.equal(fits,true,'Card must not overflow on a narrow screen');
    const editor=await page.evaluate(()=>{const x=customElements.get('motorvarmare-card').getConfigElement();x.setConfig({});x.hass=window.hass;document.body.appendChild(x);return x.localName;});
    assert.equal(editor,'motorvarmare-card-editor');
    assert.match(await page.locator('motorvarmare-card-editor').innerText().catch(()=>''),/^$/); // Content is in shadow DOM.
    assert.equal(await page.locator('motorvarmare-card-editor').locator('label').first().innerText(),'Card title');
    assert.deepEqual(errors,[]);
    console.log('PASS: seven-day calendar, multiple departures, start/stop, create, delete and Swedish/English');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
