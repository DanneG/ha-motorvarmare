const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function checkCalendarSelection(page, garage, norr, language, mobile) {
  const swedish = language === 'sv';
  const today = '2026-11-20';
  const monday = '2026-11-23';
  const tuesday = '2026-11-24';
  const dayButton = (card, key) => card.locator(`[data-mobile-day="${key}"]`);
  const todayText = swedish ? /i dag/i : /today/i;
  const mondayText = swedish ? /mån.*23 nov/i : /Mon.*23 Nov/i;
  const goToday = swedish ? 'Till i dag' : 'Go to today';
  for (const card of [garage, norr]) {
    const current = dayButton(card, today);
    assert.equal(await current.getAttribute('aria-current'), 'date');
    assert.equal(await current.getAttribute('aria-pressed'), 'true', 'Both cars open on today although their next departure is Monday');
    assert.match(await current.innerText(), todayText, 'The current date has a visible, localized label');
    assert.match(await card.locator('#new-departure').innerText(), todayText);
    assert.match(await card.locator('.mobile-add').innerText(), todayText);
    assert.match(await card.locator('.mobile-events').innerText(), swedish ? /inga? |ingen /i : /no /i);
  }
  await garage.locator('#new-departure').click();
  assert.equal(await garage.locator('#calendar-date').inputValue(), today);
  await garage.locator('#cancel-calendar').click();
  await dayButton(garage, monday).click();
  assert.equal(await dayButton(garage, today).getAttribute('aria-current'), 'date', 'Today remains independently marked');
  assert.equal(await dayButton(garage, today).getAttribute('aria-pressed'), 'false');
  assert.equal(await dayButton(garage, monday).getAttribute('aria-pressed'), 'true');
  assert.notEqual(await dayButton(garage, monday).getAttribute('aria-current'), 'date');
  assert.equal(await dayButton(norr, today).getAttribute('aria-pressed'), 'true', 'Choosing a day on Garage must not change Norr');
  assert.match(await garage.locator('#new-departure').innerText(), mondayText);
  assert.match(await garage.locator('.mobile-add').innerText(), mondayText);
  await garage.locator('.mobile-add').click();
  assert.equal(await garage.locator('#calendar-date').inputValue(), monday);
  await garage.locator('#calendar-date').fill(tuesday);
  await garage.locator('#calendar-time').fill('09:15');
  const saveText = await garage.locator('#add-calendar').innerText();
  assert.match(saveText, swedish ? /Spara.*tis.*24 nov.*kl\.\s*09:15/i : /Save.*Tue.*24 Nov.*at\s+09:15/i);
  assert.equal(await garage.locator('#calendar-time').evaluate(el => el.getRootNode().activeElement === el), true, 'Updating the save label keeps focus in the time field');
  await garage.locator('#cancel-calendar').click();
  await page.evaluate(() => {
    const ha = window.mockHA;
    const status = ha.states['sensor.garage'];
    ha.states = {...ha.states, 'sensor.garage': {...status, attributes: {...status.attributes, temperature: -2}}};
    document.querySelector('motorvarmare-overview').hass = {...ha};
  });
  assert.equal(await dayButton(garage, monday).getAttribute('aria-pressed'), 'true');
  await garage.locator('#open-calendar').click();
  const dialog = garage.locator('dialog[open]');
  if (mobile) {
    assert.equal(await dialog.locator('[data-grid-day]').getAttribute('data-grid-day'), monday, 'The expanded day view opens on the same date');
    await dialog.locator('[data-calendar-mode="week"]').click();
  }
  const weekDay = key => dialog.locator(`[data-grid-select-day="${key}"]`);
  assert.equal(await weekDay(today).getAttribute('aria-current'), 'date');
  assert.equal(await weekDay(monday).getAttribute('aria-pressed'), 'true');
  await weekDay(tuesday).click();
  await dialog.locator('#close-calendar').click();
  assert.equal(await dayButton(garage, tuesday).getAttribute('aria-pressed'), 'true', 'Week header selection is reflected on the card');
  await garage.getByRole('button', {name: goToday, exact: true}).click();
  assert.equal(await dayButton(garage, today).getAttribute('aria-pressed'), 'true');
  assert.equal(await page.evaluate(() => window.calls.filter(c => c.domain || c.type === 'calendar/event/create').length), 0, 'Date selection and cancellation must not create a departure');
}

async function check(browser, width, mobile) {
  const page = await browser.newPage({ viewport: { width, height: 830 }, isMobile: mobile, hasTouch: mobile, timezoneId:'America/Los_Angeles' });
  const language = width === 844 ? 'en' : 'sv';
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.clock.install({time:new Date('2026-11-20T10:00:00Z')});
  await page.setContent('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px Arial}main{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;padding:8px}ha-card,motorvarmare-card{display:block;min-width:0}aside{height:600px}</style><main></main><aside></aside>');
  await page.addScriptTag({path:path.resolve(__dirname,'../../custom_components/motorvarmare/www/ha-motorvarmare-card.js')});
  await page.evaluate(language => {
    window.calls = [];
    const states = {};
    const entity = (id,state,attributes={}) => states[id]={entity_id:id,state,attributes};
    window.mockHA = {
      language, locale:{language}, config:{time_zone:'Europe/Stockholm'}, states,
      async callService(domain,service,data){window.calls.push({domain,service,data});},
      async callWS(data){window.calls.push(data);return {events:[],calendar_error:false};}
    };
    for(const id of ['garage','norr']) {
      const controls = {heater_switch:'switch.'+id,calendar:'calendar.'+id,start_now:'button.start_'+id,stop_now:'button.stop_'+id,extend_30:'button.extend_'+id};
      entity(controls.heater_switch,'off');
      entity(controls.calendar,'off');
      for(const key of ['start_now','stop_now','extend_30']) entity(controls[key],'unknown');
      const event={departure:'2026-11-23T06:50:00Z',start:'2026-11-23T05:41:00Z',end:'2026-11-23T06:50:00Z',source:'Planerad',duration_minutes:69};
      entity('sensor.'+id,'waiting_to_start',{friendly_name:id,control_entities:controls,temperature:-1.4,current_duration_minutes:69,next_departure:event.departure,planned_start:event.start,schedule_7_days:[event],schedule_query_supported:true});
    }
    const overview=document.createElement('motorvarmare-overview');
    overview.setConfig({entities:['sensor.garage','sensor.norr'],layout:'cards'});
    overview.hass=window.mockHA;
    document.querySelector('main').appendChild(overview);
  }, language);
  const cards=page.locator('motorvarmare-card'), left=cards.nth(0), right=cards.nth(1);
  assert.equal(await cards.count(),2);
  const positions=await cards.evaluateAll(els=>els.map(el=>({x:el.offsetLeft,y:el.offsetTop,width:el.clientWidth})));
  assert.ok(positions.every(p=>p.width>=360));
  if(width>=800) assert.equal(positions[0].y,positions[1].y);
  else assert.ok(positions[1].y>positions[0].y);
  assert.deepEqual(await cards.locator('.title').allTextContents(),['garage','norr']);
  await checkCalendarSelection(page, left, right, language, width < 600);
  await left.locator('#start-now').click({timeout:3500});
  await right.locator('#start-now').click({timeout:3500});
  assert.deepEqual(await page.evaluate(()=>window.calls.filter(x=>x.domain).map(x=>x.data.entity_id)),['button.start_garage','button.start_norr']);
  await right.locator('[data-main-tab="energy"]').click();
  assert.equal(await left.locator('[data-main-tab="calendar"]').getAttribute('aria-pressed'),'true');
  await left.locator('#open-calendar').click();
  assert.equal(await left.locator('dialog[open]').count(),1);
  assert.equal(await right.locator('dialog').count(),0);
  await left.locator('#close-calendar').click();
  const day=left.locator('[data-mobile-day="2026-11-25"]');
  await day.click();
  await left.locator('#new-departure').click();
  assert.equal(await left.locator('#calendar-date').inputValue(),'2026-11-25');
  await left.locator('#calendar-date').fill('2026-11-25');
  await left.locator('#calendar-time').fill('08:15');
  await left.locator('#add-calendar').click();
  const calls=await page.evaluate(()=>window.calls);
  const evt=calls.find(x=>x.service==='create_event'||x.type==='calendar/event/create');
  assert.equal(evt?.data?.entity_id||evt?.entity_id,'calendar.garage',JSON.stringify(calls));
  await page.evaluate(()=>{
    const ha=window.mockHA;
    const status=ha.states['sensor.norr'];
    ha.states={...ha.states,'switch.norr':{...ha.states['switch.norr'],state:'on'},'sensor.norr':{...status,state:'heating',attributes:{...status.attributes,
      owned:true,can_extend:true,active_started_at:'2026-11-20T09:00:00Z',active_until:'2026-11-20T11:00:00Z',active_max_until:'2026-11-20T13:00:00Z'}}};
    document.querySelector('motorvarmare-overview').hass={...ha};
  });
  assert.equal(await left.locator('#start-now').count(),1);
  const actions=await right.locator('.active-actions').boundingBox();
  const timeline=await right.locator('.active-timeline').boundingBox();
  assert.ok(actions.y + actions.height <= timeline.y + 1);
  await right.locator('#extend-30').click({timeout:3500});
  await right.locator('#stop-now').click({timeout:3500});
  assert.deepEqual(await page.evaluate(()=>window.calls.slice(-2).map(x=>x.data.entity_id)),['button.extend_norr','button.stop_norr']);
  const scroll=await page.evaluate(async()=>{
    const ha=window.mockHA;
    window.scrollTo(0,Math.min(500,document.documentElement.scrollHeight-innerHeight));
    await new Promise(requestAnimationFrame);
    const start=window.scrollY;
    for(let n=0;n<6;n++){
      const status=ha.states['sensor.norr'];
      ha.states={...ha.states,'sensor.norr':{...status,attributes:{...status.attributes,temperature:-1.4+n/10}}};
      document.querySelector('motorvarmare-overview').hass={...ha};
      await new Promise(requestAnimationFrame);
    }
    return [start,window.scrollY];
  });
  assert.ok(scroll[0]>0 && Math.abs(scroll[0]-scroll[1])<3,JSON.stringify(scroll));
  if (width === 390) {
    await right.locator('[data-main-tab="calendar"]').click();
    await left.locator('[data-mobile-day="2026-11-25"]').click();
    await page.clock.setSystemTime(new Date('2026-11-20T22:59:55Z'));
    await page.clock.fastForward(65_000);
    for (const card of [left, right]) {
      assert.equal(await card.locator('[data-mobile-day][aria-current="date"]').getAttribute('data-mobile-day'),'2026-11-21','Midnight follows the Home Assistant timezone even without sensor updates');
    }
    assert.equal(await right.locator('[data-mobile-day][aria-pressed="true"]').getAttribute('data-mobile-day'),'2026-11-21','The untouched calendar follows today');
    assert.equal(await left.locator('[data-mobile-day][aria-pressed="true"]').getAttribute('data-mobile-day'),'2026-11-25','An explicit future day survives midnight');
  }
  assert.deepEqual(errors,[]);
  console.log(width+'px: start/extend/stop isolated, tabs/modal independent, departure for garage only, scroll '+JSON.stringify(scroll));
  await page.close();
}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});try{for(const width of [1096,390,844])await check(browser,width,width<1000);}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
