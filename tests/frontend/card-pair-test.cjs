const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function check(browser, width, mobile) {
  const page = await browser.newPage({ viewport: { width, height: 830 }, isMobile: mobile, hasTouch: mobile });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.clock.setFixedTime(new Date('2026-11-20T10:00:00Z'));
  await page.setContent('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px Arial}main{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;padding:8px}ha-card,motorvarmare-card{display:block;min-width:0}aside{height:600px}</style><main></main><aside></aside>');
  await page.addScriptTag({path:path.resolve(__dirname,'../../custom_components/motorvarmare/www/ha-motorvarmare-card.js')});
  await page.evaluate(() => {
    window.calls = [];
    const states = {};
    const entity = (id,state,attributes={}) => states[id]={entity_id:id,state,attributes};
    window.mockHA = {
      language:'sv', locale:{language:'sv'}, config:{time_zone:'Europe/Stockholm'}, states,
      async callService(domain,service,data){window.calls.push({domain,service,data});},
      async callWS(data){window.calls.push(data);return {events:[],calendar_error:false};}
    };
    for(const id of ['garage','norr']) {
      const controls = {heater_switch:'switch.'+id,calendar:'calendar.'+id,start_now:'button.start_'+id,stop_now:'button.stop_'+id,extend_30:'button.extend_'+id};
      entity(controls.heater_switch,'off');
      entity(controls.calendar,'off');
      for(const key of ['start_now','stop_now','extend_30']) entity(controls[key],'unknown');
      entity('sensor.'+id,'waiting_to_start',{friendly_name:id,control_entities:controls,temperature:-1.4,current_duration_minutes:69,next_departure:'2026-11-23T06:50:00Z',planned_start:'2026-11-23T05:41:00Z',schedule_7_days:[],schedule_query_supported:true});
    }
    const overview=document.createElement('motorvarmare-overview');
    overview.setConfig({entities:['sensor.garage','sensor.norr'],layout:'cards'});
    overview.hass=window.mockHA;
    document.querySelector('main').appendChild(overview);
  });
  const cards=page.locator('motorvarmare-card'), left=cards.nth(0), right=cards.nth(1);
  assert.equal(await cards.count(),2);
  const positions=await cards.evaluateAll(els=>els.map(el=>({x:el.offsetLeft,y:el.offsetTop,width:el.clientWidth})));
  assert.ok(positions.every(p=>p.width>=360));
  if(width>=800) assert.equal(positions[0].y,positions[1].y);
  else assert.ok(positions[1].y>positions[0].y);
  assert.deepEqual(await cards.locator('.title').allTextContents(),['garage','norr']);
  await left.locator('#start-now').click({timeout:3500});
  await right.locator('#start-now').click({timeout:3500});
  assert.deepEqual(await page.evaluate(()=>window.calls.map(x=>x.data.entity_id)),['button.start_garage','button.start_norr']);
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
  assert.deepEqual(errors,[]);
  console.log(width+'px: start/extend/stop isolated, tabs/modal independent, departure for garage only, scroll '+JSON.stringify(scroll));
  await page.close();
}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});try{for(const width of [1096,390,844])await check(browser,width,width<1000);}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
