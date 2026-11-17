/* Run with Playwright on NODE_PATH and Chrome installed. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:440,height:1100}});
    await page.clock.setFixedTime(new Date('2026-11-06T08:31:00Z'));
    const errors=[];
    page.on('pageerror', error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:`body{margin:0;padding:16px;background:#1a1b1c;font-family:Roboto,Arial,sans-serif}motorvarmare-card{display:block;--primary-text-color:#e8eaed;--secondary-text-color:#b8c0cb;--card-background-color:#171717;--secondary-background-color:#292a2d;--divider-color:#3c4043;--primary-color:#03a9d3;--text-primary-color:#fff;--error-color:#ff8585}`});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{connectedCallback(){Object.assign(this.style,{display:'block',background:'var(--card-background-color)',borderRadius:'15px'});}});
      customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent='♨';}});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.heater',start_now:'button.start',stop_now:'button.stop',calendar:'calendar.schedule',manual_departure:'datetime.manual',clear_departure:'button.clear',weekly_times:Array.from({length:7},(_,i)=>`time.car_${i}`),weekly_enabled:Array.from({length:7},(_,i)=>`switch.car_${i}`)};
      const states={
        'sensor.car_status':{entity_id:'sensor.car_status',state:'heating',attributes:{friendly_name:'Bil 1 Status',control_entities:controls,temperature:-4,current_duration_minutes:36,owned:true,active_until:'2026-11-06T10:00:00+01:00',next_departure:'2026-11-06T10:00:00+01:00',planned_start:'2026-11-06T09:24:00+01:00',source:'Planerad',schedule_7_days:[{departure:'2026-11-06T10:00:00+01:00',start:'2026-11-06T09:24:00+01:00',source:'Planerad',duration_minutes:36}]}},
        'switch.heater':{entity_id:'switch.heater',state:'on',attributes:{}},
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
      window.changeAttrs = values=>{Object.assign(window.hass.states['sensor.car_status'].attributes,values); card.hass={...window.hass};};
    });
    const card=page.locator('motorvarmare-card');
    await card.locator('[data-main-tab="energy"]').click();
    assert.equal(await card.locator('.power-stat').count(),0,'Power is optional');
    assert.equal(await card.locator('.energy-stat').count(),0,'Energy is optional');
    await page.evaluate(()=>window.changeAttrs({power_sensor_configured:true,energy_sensor_configured:true,power_w:1185.2,session_energy_kwh:0.137,energy_sensor_available:true,energy_monitor_status:'ok',alarm_active:false}));
    assert.match(await card.locator('.power-stat').innerText(),/1\s?185,2\s*W/);
    assert.match(await card.locator('.energy-stat').innerText(),/0,137\s*kWh/);
    assert.equal(await card.locator('.power-alarm').count(),0);
    await page.evaluate(()=>window.changeAttrs({
      next_estimated_energy_kwh:1.2,next_estimated_cost:2.4,next_estimated_currency:'SEK',next_estimate_basis:'latest_complete_session_average',
      heating_history:[{start:'2026-11-05T05:00:00Z',end:'2026-11-05T06:00:00Z',complete:true,duration_minutes:60,energy_kwh:0.5,temperature_at_start_c:-5.2}],
      power_deviation_active:true,power_deviation_direction:'high'
    }));
    assert.match(await card.locator('.next-estimate').innerText(),/1,20\s*kWh/);
    assert.match(await card.locator('.next-estimate').innerText(),/2,40\s*SEK/);
    assert.match(await card.locator('.next-estimate').innerText(),/senaste fullständiga värmningen/);
    assert.match(await card.locator('.history-entry').first().innerText(),/Utetemperatur vid start: −?[-−]?5,2\s*°C/);
    assert.match(await card.locator('.power-deviation').innerText(),/högre än det inställda normalintervallet/);
    await card.locator('[data-main-tab="calendar"]').click();
    await card.locator('#open-calendar').click();
    assert.match(await card.locator('#calendar-expanded').innerText(),/högre än det inställda normalintervallet/);
    await card.locator('#close-calendar').click();
    await card.locator('[data-main-tab="energy"]').click();
    await page.evaluate(()=>window.changeAttrs({next_estimate_basis:null,power_deviation_active:false}));
    assert.equal(await card.locator('.next-estimate').count(),0,'A forecast without a known basis must not be shown');
    assert.equal(await card.locator('.power-deviation').count(),0);
    if (process.env.MOTORVARMARE_ENERGY_PREVIEW_PATH) await page.screenshot({path:process.env.MOTORVARMARE_ENERGY_PREVIEW_PATH,fullPage:true});
    await page.evaluate(()=>window.changeAttrs({power_w:0,energy_monitor_status:'low_power',alarm_active:true}));
    assert.match(await card.locator('.power-stat').innerText(),/0\s*W/,'Zero must be displayed as a measurement');
    assert.match(await card.locator('.power-alarm').innerText(),/Kontrollera att motorvärmarkabeln är ansluten/);
    // An actionable alert must remain visible even when the energy view is not selected.
    await card.locator('[data-main-tab="calendar"]').click();
    assert.equal(await card.locator('.power-alarm').isVisible(),true,'Low-power alarm must be visible outside the energy view');
    await card.locator('[data-main-tab="energy"]').click();
    if (process.env.MOTORVARMARE_ALARM_PREVIEW_PATH) await page.screenshot({path:process.env.MOTORVARMARE_ALARM_PREVIEW_PATH,fullPage:true});
    await page.evaluate(()=>{window.hass.states['switch.heater'].state='off';window.changeAttrs({});});
    assert.equal(await card.locator('.power-alarm').count(),0,'A stale alert must not say the heater is on after the switch turns off');
    await page.evaluate(()=>{window.hass.states['switch.heater'].state='on';window.changeAttrs({energy_monitor_status:'power_unavailable'});});
    assert.equal(await card.locator('.power-alarm').count(),0,'A stale alert must not claim low power when the sensor is unavailable');
    await page.evaluate(()=>window.changeAttrs({power_w:null,energy_monitor_status:'power_unavailable',alarm_active:false,energy_sensor_available:false}));
    assert.match(await card.locator('.power-stat').innerText(),/–/);
    assert.equal(await card.locator('.power-alarm').count(),0,'Unavailable power is not a low-power alarm');
    assert.match(await card.locator('.wrap').innerText(),/Effektsensorn är inte tillgänglig/);
    assert.match(await card.locator('.wrap').innerText(),/Visat värde är det senaste kända/);
    await page.evaluate(()=>window.changeAttrs({energy_session_status:'incomplete',energy_sensor_available:true,session_energy_kwh:0.4567}));
    assert.match(await card.locator('.energy-stat').innerText(),/–/,'An incomplete session must never appear as a complete energy value');
    assert.match(await card.locator('.wrap').innerText(),/Energimätningen för körningen är ofullständig/);
    await page.evaluate(()=>window.changeAttrs({energy_session_status:'no_session',session_energy_kwh:null}));
    assert.match(await card.locator('.wrap').innerText(),/Ingen energimätning för en körning ännu/);
    await page.evaluate(()=>{window.hass.locale.language='en';window.changeAttrs({power_w:null,session_energy_kwh:null,energy_sensor_available:false,energy_monitor_status:'waiting'});});
    assert.match(await card.locator('.power-stat').innerText(),/Current power/);
    assert.match(await card.locator('.energy-stat').innerText(),/Estimated energy, current\/last session/);
    assert.match(await card.locator('.wrap').innerText(),/Waiting for power measurement/);
    assert.match(await card.locator('.wrap').innerText(),/Energy calculation is unavailable/);
    await page.evaluate(()=>window.changeAttrs({power_sensor_configured:false,energy_sensor_configured:true,energy_sensor_available:true,energy_session_status:'complete',session_energy_kwh:0}));
    assert.equal(await card.locator('.power-stat').count(),0,'Power and energy sources are independently optional');
    assert.match(await card.locator('.energy-stat').innerText(),/0\.00\s*kWh/);
    assert.equal(await card.locator('.power-alarm').count(),0);
    assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Energy layout must fit a narrow card');
    assert.deepEqual(errors,[]);
    console.log('PASS: optional power and energy, unavailable values, low-power alarm and translations');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
