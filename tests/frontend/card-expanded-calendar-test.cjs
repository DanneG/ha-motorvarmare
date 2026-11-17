/* Expanded calendar: real user interactions on mobile and desktop. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');

async function exercise(browser,width) {
  const page=await browser.newPage({viewport:{width,height:780},isMobile:width<600,hasTouch:width<600});
  const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  await page.clock.setFixedTime(new Date('2026-11-05T08:00:00Z'));
  await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="dashboard"><div class="before">Other cards</div><motorvarmare-card></motorvarmare-card><div class="after">Other cards</div></div></body></html>');
  await page.addStyleTag({content:'html,body{margin:0}#dashboard{height:100dvh;overflow:auto;font-family:Arial}.before{height:500px}.after{height:1200px}motorvarmare-card,ha-card{display:block}motorvarmare-card{margin:0 auto;width:min(100%,700px);--primary-text-color:#eee;--secondary-text-color:#bbb;--card-background-color:#17191b;--secondary-background-color:#293038;--divider-color:#555;--primary-color:#08bcd4;--text-primary-color:#111;background:#17191b}'});
  await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{});});
  await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
  await page.evaluate(()=>{
    const controls={heater_switch:'switch.heater',calendar:'calendar.car',start_now:'button.start',stop_now:'button.stop',manual_departure:'datetime.manual',clear_departure:'button.clear',weekly_times:[],weekly_enabled:[]};
    const attrs={friendly_name:'Bil Status',control_entities:controls,temperature:-5,current_duration_minutes:90,schedule_query_supported:true,schedule_7_days:[
      {departure:'2026-11-05T10:00:00+01:00',start:'2026-11-05T08:30:00+01:00',end:'2026-11-05T10:00:00+01:00',source:'Planerad',uid:'first',removable:true},
      {departure:'2026-11-05T15:00:00+01:00',start:'2026-11-05T13:30:00+01:00',end:'2026-11-05T15:00:00+01:00',source:'Planerad',uid:'second',removable:true},
      {departure:'2026-11-05T12:00:00+01:00',start:'2026-11-05T11:55:00+01:00',end:'2026-11-05T12:00:00+01:00',source:'Planerad',uid:'short',removable:true}],heating_history:[]};
    const states={'sensor.status':{entity_id:'sensor.status',state:'waiting_to_start',attributes:attrs},'switch.heater':{state:'off',attributes:{}},'calendar.car':{state:'off',attributes:{}},'button.start':{state:'unknown',attributes:{}},'button.stop':{state:'unknown',attributes:{}},'datetime.manual':{state:'unknown',attributes:{}},'button.clear':{state:'unknown',attributes:{}}};
    window.calls=[];window.serverEvents=[...attrs.schedule_7_days];
    window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(domain,service,data){window.calls.push({domain,service,data});},async callWS(message){window.calls.push({ws:message});if(message.type==='motorvarmare/get_schedule')return {events:window.serverEvents,calendar_error:false};if(message.type==='calendar/event/create'){window.serverEvents.push({departure:message.event.dtstart,start:new Date(Date.parse(message.event.dtstart)-5400000).toISOString(),end:message.event.dtstart,source:'Planerad',uid:'added-'+window.serverEvents.length,removable:true});return {uid:'added'};}if(message.type==='calendar/event/delete')window.serverEvents=window.serverEvents.filter(event=>event.uid!==message.uid);return {};}};
    const card=document.querySelector('motorvarmare-card');card.setConfig({status_entity:'sensor.status',title:'Bil'});card.hass=window.hass;
  });
  const card=page.locator('motorvarmare-card'),dashboard=page.locator('#dashboard');
  const open=card.locator('#open-calendar'),modal=card.locator('#calendar-expanded');
  await open.scrollIntoViewIfNeeded();
  const before=await dashboard.evaluate(el=>el.scrollTop);
  assert.match(await open.innerText(),/kalender/i);
  await open.click();
  assert.equal(await modal.isVisible(),true,'Expanded calendar must be visible');
  assert.equal(await modal.evaluate(el=>el.open),true,'Expanded calendar must be an actual open dialog');
  assert.equal(await modal.locator('#close-calendar').evaluate(el=>el.getRootNode().activeElement===el),true,'Opening the modal places focus inside it');
  await page.evaluate(()=>{window.modalReference=document.querySelector('motorvarmare-card').shadowRoot.querySelector('#calendar-expanded');});
  for (let n=0;n<8;n++) {
    await page.keyboard.press('Tab');
    assert.equal(await modal.evaluate(el=>el.contains(el.getRootNode().activeElement)),true,'Keyboard focus must remain inside the modal');
  }
  assert.equal(await modal.locator('[data-grid-day]').count(),7,'Week has seven columns');
  assert.ok(await modal.locator('.cal-hour').count()>=24,'Time axis contains daily hours');
  const days=await modal.locator('[data-grid-day]').evaluateAll(nodes=>nodes.map(node=>node.dataset.gridDay));
  assert.deepEqual(days,['2026-11-05','2026-11-06','2026-11-07','2026-11-08','2026-11-09','2026-11-10','2026-11-11']);
  assert.equal(await modal.locator('[data-departure]').count(),3,'All departures appear in the expanded view');
  assert.match(await modal.innerText(),/08:30/);assert.match(await modal.innerText(),/15:00/);
  // Update Home Assistant while the modal is open. It must stay open and not
  // reset the user's week, focus or the dashboard scroll position.
  await page.evaluate(()=>{const h=window.hass;const s=h.states['sensor.status'];document.querySelector('motorvarmare-card').hass={...h,states:{...h.states,'sensor.status':{...s,attributes:{...s.attributes,temperature:-6}}}};});
  assert.equal(await modal.evaluate(el=>el.open),true);
  assert.equal(await modal.evaluate(el=>el===window.modalReference),true,'A state update must not replace the open modal');
  assert.ok(Math.abs((await dashboard.evaluate(el=>el.scrollTop))-before)<3,'Underlying dashboard must stay in place while open');
  await page.evaluate(()=>{const h=window.hass,a=h.states['sensor.status'].attributes;Object.assign(a,{power_sensor_configured:true,energy_monitor_status:'low_power',alarm_active:true,error:'Kalendern kan inte läsas'});h.states['switch.heater'].state='on';document.querySelector('motorvarmare-card').hass={...h};});
  assert.match(await modal.innerText(),/motorvärmarkabeln/i,'The cable warning must remain visible inside the dialog');
  assert.match(await modal.innerText(),/kalendern kan inte läsas/i,'Calendar errors must remain visible inside the dialog');
  await page.evaluate(()=>{const h=window.hass,a=h.states['sensor.status'].attributes;Object.assign(a,{alarm_active:false,error:null});h.states['switch.heater'].state='off';document.querySelector('motorvarmare-card').hass={...h};});
  // Very short blocks can be too small to tap. The open list remains a
  // reliable way to edit and remove the same departure.
  await modal.locator('.cal-agenda summary').click();
  assert.equal(await modal.locator('.cal-agenda').evaluate(el=>el.open),true);
  assert.equal(await modal.locator('.cal-agenda [data-remove-uid="short"]').isVisible(),true);
  await modal.locator('.cal-agenda button[data-edit-index="1"]').click();
  assert.equal(await modal.locator('#calendar-time').inputValue(),'12:00');
  await modal.locator('#cancel-calendar').click();
  await modal.locator('.cal-agenda [data-remove-uid="short"]').click();
  assert.ok(await page.evaluate(()=>window.calls.some(x=>x.ws?.type==='calendar/event/delete' && x.ws.uid==='short')));
  // Local calendar blocks are directly editable without leaving the dialog.
  await modal.locator('.cal-event button[data-edit-index]').first().click();
  assert.equal(await modal.locator('#calendar-time').inputValue(),'10:00');
  await modal.locator('#calendar-time').fill('10:15');
  await modal.locator('#add-calendar').click();
  const update=await page.evaluate(()=>window.calls.find(x=>x.ws?.type==='calendar/event/update'));
  assert.equal(update.ws.uid,'first');
  assert.equal(update.ws.event.dtstart,'2026-11-05T09:15:00.000Z');
  await modal.locator('#window-next').click();
  await page.waitForFunction(()=>window.calls.some(x=>x.ws?.type==='motorvarmare/get_schedule' && x.ws.start==='2026-11-12'));
  assert.equal(await modal.locator('[data-grid-day]').first().getAttribute('data-grid-day'),'2026-11-12');
  await modal.locator('#window-today').click();
  assert.equal(await modal.locator('[data-grid-day]').first().getAttribute('data-grid-day'),'2026-11-05');
  // Opening a day in the grid creates a normal editor in the large view.
  const scroll=modal.locator('.cal-scroll');
  await scroll.evaluate(el=>{el.scrollTop=8*64;el.scrollLeft=0;});
  const grid=modal.locator('[data-grid-day="2026-11-06"]');
  const point=await grid.evaluate((el)=>{const rect=el.getBoundingClientRect();const port=el.closest('.cal-scroll').getBoundingClientRect();return {x:Math.max(rect.left+12,port.left+55),y:port.top+130};});
  await page.mouse.click(point.x,point.y);
  const editor=modal.locator('#calendar-date');
  assert.equal(await editor.isVisible(),true,'Clicking the grid must open the departure editor');
  await editor.fill('2026-11-07');
  await modal.locator('#calendar-time').fill('09:00');
  await modal.locator('#repeat-frequency').selectOption('WEEKLY');
  await modal.locator('[data-repeat-day="SA"]').check();
  await modal.locator('#repeat-until').fill('2026-12-05');
  await modal.locator('#add-calendar').click();
  const first=await page.evaluate(()=>window.calls.find(x=>x.ws?.type==='calendar/event/create'));
  assert.equal(first.ws.event.dtstart,'2026-11-07T08:00:00.000Z');
  assert.match(first.ws.event.rrule,/FREQ=WEEKLY/);assert.match(first.ws.event.rrule,/BYDAY=.*SA/);
  assert.ok(first.ws.event.rrule.includes('UNTIL='),'Repeat rule must retain its end date');
  await modal.locator('#calendar-date').waitFor({state:'hidden'});
  // Add a second independent departure on that same date.
  await scroll.evaluate(el=>{el.scrollTop=8*64;el.scrollLeft=0;});
  const secondPoint=await grid.evaluate(el=>{const rect=el.getBoundingClientRect();const port=el.closest('.cal-scroll').getBoundingClientRect();return {x:Math.max(rect.left+12,port.left+55),y:port.top+130};});
  await page.mouse.click(secondPoint.x,secondPoint.y);
  await modal.locator('#calendar-date').fill('2026-11-07');
  await modal.locator('#calendar-time').fill('13:30');
  await modal.locator('#repeat-frequency').selectOption('NONE');
  await modal.locator('#add-calendar').click();
  const second=await page.evaluate(()=>window.calls.find(x=>x.domain==='calendar' && x.service==='create_event'));
  assert.ok(second,'A second one-time departure can be created on the same day');
  assert.equal(second.data.start_date_time,'2026-11-07T13:30:00');
  // The close control returns focus to the originating button and does not
  // teleport the dashboard to its top.
  await modal.locator('#close-calendar').click();
  assert.equal(await modal.isVisible(),false);
  assert.equal(await open.evaluate(el=>el.getRootNode().activeElement===el),true,'Focus returns to the open button');
  assert.ok(Math.abs((await dashboard.evaluate(el=>el.scrollTop))-before)<3,'Closing the modal must preserve dashboard scroll');
  await open.click();
  await page.keyboard.press('Escape');
  assert.equal(await modal.isVisible(),false,'Escape closes the modal');
  assert.equal(await open.evaluate(el=>el.getRootNode().activeElement===el),true);
  await page.evaluate(()=>{window.hass.locale.language='en';document.querySelector('motorvarmare-card').hass={...window.hass};});
  assert.match(await open.innerText(),/calendar/i,'Calendar action is translated');
  await open.click();
  assert.match(await modal.innerText(),/calendar/i,'Expanded calendar is translated');
  await modal.locator('#close-calendar').click();
  assert.deepEqual(errors,[]);
  await page.close();
}
async function main(){const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});try{await exercise(browser,390);await exercise(browser,1200);console.log('PASS: expanded calendar mobile/desktop, dates, create recurrence, language, focus and scroll');}finally{await browser.close();}}
main().catch(error=>{console.error(error);process.exitCode=1;});
