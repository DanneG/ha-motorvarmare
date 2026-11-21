/* Run with Playwright on NODE_PATH and Chrome installed. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:1360,height:1100}});
    await page.clock.setFixedTime(new Date('2026-11-05T06:00:00Z'));
    const errors=[];
    page.on('pageerror', error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:`body{margin:0;background:#1a1b1c;padding:16px;font-family:Roboto,Arial,sans-serif} motorvarmare-card{--primary-text-color:#e8eaed;--secondary-text-color:#b8c0cb;--card-background-color:#171717;--secondary-background-color:#292a2d;--divider-color:#3c4043;--primary-color:#03a9d3;--text-primary-color:#fff;display:block;width:1100px;margin:auto}`});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{connectedCallback(){Object.assign(this.style,{display:'block',background:'var(--card-background-color)',borderRadius:'15px'});}});
      customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent='♨';}});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    const fixture=await page.evaluate(()=>{
      const controls={manual_departure:'datetime.car_manual',clear_departure:'button.car_clear',heater_switch:'switch.car_heater',calendar:'calendar.car_schedule',start_now:'button.car_start',stop_now:'button.car_stop',weekly_times:Array.from({length:7},(_,i)=>`time.car_${i}`),weekly_enabled:Array.from({length:7},(_,i)=>`switch.car_${i}`)};
      const states={
        'sensor.car_status':{entity_id:'sensor.car_status',state:'waiting_to_start',attributes:{friendly_name:'Bil 1 Status',control_entities:controls,temperature:1,current_duration_minutes:29,owned:false,schedule_7_days:[]}},
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
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(domain,service,data){window.calls.push({domain,service,data});},async callWS(data){window.calls.push({ws:data});}};
      const card=document.createElement('motorvarmare-card');
      card.setConfig({status_entity:'sensor.car_status',title:'Bil 1'});
      card.hass=window.hass;
      document.body.appendChild(card);
      const keys=card._dayKeys();
      // The first departure is at 10:00. A later departure on the third
      // visible day crosses midnight; the latter must not force the initial
      // calendar position to 00:00 or change the initially selected day.
      return {today:keys[0],tomorrow:keys[1],third:keys[2],fourth:keys[3]};
    });
    const card=page.locator('motorvarmare-card');
    await page.evaluate(({today,tomorrow,third})=>{
      const attrs=window.hass.states['sensor.car_status'].attributes;
      attrs.schedule_7_days=[
        {departure:`${today}T10:00:00+01:00`,start:`${today}T09:31:00+01:00`,source:'Kalender',duration_minutes:29},
        {departure:`${today}T15:00:00+01:00`,start:`${today}T14:31:00+01:00`,source:'Planerad',uid:'afternoon',removable:true,duration_minutes:29},
        {departure:`${third}T00:20:00+01:00`,start:`${tomorrow}T23:40:00+01:00`,source:'Planerad',uid:'overnight',removable:true,duration_minutes:40},
      ];
      attrs.next_departure=attrs.schedule_7_days[0].departure;
      attrs.planned_start=attrs.schedule_7_days[0].start;
      attrs.duration_minutes=29;
      attrs.source='Kalender';
      document.querySelector('motorvarmare-card').hass={...window.hass};
    },fixture);
    await page.waitForTimeout(100);
    const initialScroll=await card.locator('.cal-scroll').evaluate(el=>el.scrollTop);
    assert.ok(initialScroll>=400 && initialScroll<700,`Delayed schedule should open near 09:31, got scrollTop=${initialScroll}`);
    await card.locator('.cal-scroll').evaluate(el=>{el.scrollTop=700;});
    const manualScroll=await card.locator('.cal-scroll').evaluate(el=>el.scrollTop);
    await page.evaluate(()=>{document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await card.locator('.cal-scroll').evaluate(el=>el.scrollTop),manualScroll,'User calendar scroll must survive HA updates');

    // This is a narrow card on a wide page, not just a small browser viewport.
    await card.evaluate(el=>{el.style.width='400px';});
    await card.locator('.mobile-day').first().waitFor({state:'visible'});
    assert.equal(await card.locator('.mobile-day').count(),7);
    assert.equal(await card.locator(`[data-mobile-day="${fixture.today}"]`).getAttribute('aria-pressed'),'true','Today remains selected after the schedule arrives');
    assert.equal(await card.locator('.mobile-events .mobile-event').count(),2,'Both departures are visible on the selected day');
    assert.match(await card.locator('.mobile-events').innerText(),/09:31/);
    assert.match(await card.locator('.mobile-events').innerText(),/10:00/);
    const widths=await card.evaluate(el=>{const root=el.shadowRoot;const v=root.querySelector('.mobile-events');return {host:el.clientWidth,hostScroll:el.scrollWidth,viewport:v.clientWidth,scroll:v.scrollWidth};});
    assert.ok(widths.hostScroll<=widths.host+1 && widths.scroll<=widths.viewport+1,'Narrow card must not need horizontal scrolling');
    if (process.env.MOTORVARMARE_MOBILE_PREVIEW_PATH) {
      await page.setViewportSize({width:440,height:1100});
      await card.evaluate(el=>{el.style.width='100%';});
      await page.screenshot({path:process.env.MOTORVARMARE_MOBILE_PREVIEW_PATH,fullPage:true});
    }
    await card.locator(`[data-mobile-day="${fixture.third}"]`).click();
    assert.equal(await card.locator(`[data-mobile-day="${fixture.third}"]`).getAttribute('aria-pressed'),'true');
    assert.match(await card.locator('.mobile-events').innerText(),/00:20/);
    await page.evaluate(()=>{document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await card.locator(`[data-mobile-day="${fixture.third}"]`).getAttribute('aria-pressed'),'true','Explicit day choice must survive HA updates');
    await card.locator(`[data-mobile-day="${fixture.fourth}"]`).click();
    await page.evaluate(()=>{document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.equal(await card.locator(`[data-mobile-day="${fixture.fourth}"]`).getAttribute('aria-pressed'),'true','A chosen day with no departures must also survive updates');
    await card.locator(`[data-mobile-day="${fixture.tomorrow}"]`).click();
    await card.locator('#new-departure').click();
    assert.equal(await card.locator('#calendar-date').inputValue(),fixture.tomorrow);
    await card.locator('#cancel-calendar').click();
    await card.locator(`[data-add-day="${fixture.tomorrow}"]:visible`).click();
    await card.locator('#calendar-time').fill('11:15');
    await card.locator('#add-calendar').click();
    const add=await page.evaluate(()=>window.calls.shift());
    assert.deepEqual(add,{domain:'calendar',service:'create_event',data:{entity_id:'calendar.car_schedule',summary:'Avresa',start_date_time:`${fixture.tomorrow}T11:15:00`,end_date_time:`${fixture.tomorrow}T11:16:00`}});
    await card.locator(`[data-mobile-day="${fixture.today}"]`).click();
    await card.locator('.mobile-events [data-remove-uid="afternoon"]').click();
    await card.locator('#commit-removal').click();
    assert.deepEqual(await page.evaluate(()=>window.calls.shift()),{ws:{type:'calendar/event/delete',entity_id:'calendar.car_schedule',uid:'afternoon'}});
    await page.evaluate(()=>{window.hass.locale.language='en';document.querySelector('motorvarmare-card').hass={...window.hass};});
    assert.match(await card.locator('.wrap').innerText(),/Next 7 days/);
    assert.match(await card.locator('.mobile-events').innerText(),/Calendar|Scheduled/);
    await page.setViewportSize({width:320,height:900});
    await card.evaluate(el=>{el.style.width='100%';});
    assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Mobile card must fit 320px viewport');

    // User choices made before Home Assistant finishes loading the calendar
    // must win over the automatic choice when the schedule arrives later.
    await page.setViewportSize({width:1360,height:1100});
    await page.evaluate(()=>{
      const a=window.hass.states['sensor.car_status'].attributes;
      const initial={...window.hass,states:{...window.hass.states,'sensor.car_status':{...window.hass.states['sensor.car_status'],attributes:{...a,schedule_7_days:[]}}}};
      for (const [id,width] of [['early-desktop','1100px'],['early-mobile','400px']]) {
        const c=document.createElement('motorvarmare-card');c.id=id;c.style.width=width;
        c.setConfig({status_entity:'sensor.car_status'});c.hass=initial;document.body.appendChild(c);
      }
    });
    const earlyDesktop=page.locator('#early-desktop'), earlyMobile=page.locator('#early-mobile');
    await earlyMobile.locator(`[data-mobile-day="${fixture.fourth}"]`).click();
    const desktopScroll=earlyDesktop.locator('.cal-scroll');
    await desktopScroll.evaluate(el=>{el.scrollTop=0;});
    await desktopScroll.hover();
    await page.mouse.wheel(0,260);
    await page.waitForTimeout(100);
    const chosenPosition=await desktopScroll.evaluate(el=>el.scrollTop);
    assert.ok(chosenPosition>0,'User wheel movement should scroll the desktop calendar');
    await page.evaluate(()=>{
      for (const id of ['early-desktop','early-mobile']) document.getElementById(id).hass={...window.hass};
    });
    assert.equal(await desktopScroll.evaluate(el=>el.scrollTop),chosenPosition,'Late calendar data must not override user scrolling');
    assert.equal(await earlyMobile.locator(`[data-mobile-day="${fixture.fourth}"]`).getAttribute('aria-pressed'),'true','Late calendar data must not override an explicitly chosen day');
    assert.ok(await earlyMobile.locator(`[data-mobile-day="${fixture.fourth}"]`).evaluate(el=>el.getRootNode().activeElement===el),'HA updates must retain keyboard focus on the chosen day');
    assert.deepEqual(errors,[]);
    console.log('PASS: adaptive narrow card, late schedule, selected day, overnight, create, remove, languages and user scroll');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
