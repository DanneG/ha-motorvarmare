/* Run with Playwright available on NODE_PATH and Chrome installed. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser=await chromium.launch({headless:true,executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page=await browser.newPage({viewport:{width:Number(process.env.MV_PREVIEW_WIDTH || 390),height:900}});
    await page.clock.install({time:new Date('2026-11-12T08:25:00Z')});
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.addStyleTag({content:'body{margin:0;padding:16px}motorvarmare-card{display:block;--primary-text-color:#eee;--secondary-text-color:#aaa;--card-background-color:#222;--secondary-background-color:#333;--divider-color:#555;--primary-color:#03a9d3;--text-primary-color:#fff}'});
    if (process.env.MV_PREVIEW_LIGHT) await page.addStyleTag({content:'body{background:#edf1f4}motorvarmare-card{max-width:800px;margin:auto;--primary-text-color:#1b2733;--secondary-text-color:#53677b;--card-background-color:#fff;--secondary-background-color:#f1f5f7;--divider-color:#d8e0e6;--primary-color:#007fac;--text-primary-color:#fff}'});
    else await page.addStyleTag({content:'body{background:#151719}motorvarmare-card{max-width:800px;margin:auto}'});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{connectedCallback(){this.style.display='block'}});
      customElements.define('ha-icon',class extends HTMLElement{});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={heater_switch:'switch.car',stop_now:'button.stop',extend_30:'button.extend',calendar:'calendar.car'};
      const attrs={friendly_name:'Bil status',control_entities:controls,owned:true,active_started_at:'2026-11-12T08:00:00Z',active_measurement_started_at:'2026-11-12T08:00:05Z',
        active_until:'2026-11-12T09:00:00Z',active_max_until:'2026-11-12T12:00:00Z',can_extend:true,
        power_sensor_configured:true,energy_sensor_configured:true,power_w:780,session_energy_kwh:0.35,active_session_cost:1.2,active_session_currency:'SEK',schedule_7_days:[],
        active_power_samples:[{at:'2026-11-12T08:00:00Z',watts:600},{at:'2026-11-12T08:05:00Z',watts:700},{at:'2026-11-12T08:10:00Z',watts:null},{at:'2026-11-12T08:15:00Z',watts:780}]};
      const states={'sensor.car':{entity_id:'sensor.car',state:'heating',attributes:attrs},'switch.car':{entity_id:'switch.car',state:'on',attributes:{}},'button.stop':{entity_id:'button.stop',state:'unknown',attributes:{}},'button.extend':{entity_id:'button.extend',state:'unknown',attributes:{}},'calendar.car':{entity_id:'calendar.car',state:'off',attributes:{}}};
      window.calls=[];window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(d,s,v){window.calls.push({d,s,v});},async callWS(){}};
      const card=document.createElement('motorvarmare-card');card.setConfig({status_entity:'sensor.car'});card.hass=window.hass;document.body.appendChild(card);
    });
    const card=page.locator('motorvarmare-card');
    assert.match(await card.locator('.active-remaining').innerText(),/35 min kvar/);
    assert.equal(await card.locator('.active-progress').getAttribute('aria-valuenow'),'42');
    assert.match(await card.locator('.active-metrics').innerText(),/780 W[\s\S]*0,35 kWh[\s\S]*1,20 SEK/);
    assert.equal(await card.locator('.active-measurement-since').count(),0,'A measurement beginning in the same displayed minute needs no second start label');
    const graphPath=await card.locator('.active-chart path').getAttribute('d');
    assert.equal(graphPath.match(/M/g).length,2,'Missing data splits the line');
    assert.match(graphPath,/M0\.00 25\.00 L26\.67 25\.00 L26\.67 16\.50/,'Use the full heating interval and hold the previous power until the next observation');
    assert.deepEqual(await card.locator('.active-axis .active-tick').allInnerTexts(),['09:00','09:30','10:00'],'The axis spans actual start through planned stop');
    for (const width of [320,1000,390]) {
      await page.setViewportSize({width,height:900});
      const timeline=await card.locator('.active-progress').boundingBox(), plot=await card.locator('.active-chart-plot').boundingBox();
      assert.ok(Math.abs(timeline.x-plot.x)<1 && Math.abs(timeline.width-plot.width)<1,`Timeline and graph share the exact axis at ${width}px`);
      const fullWidth=await card.locator('.active-timeline').boundingBox();
      assert.ok(Math.abs(timeline.x-fullWidth.x)<1 && Math.abs(timeline.width-fullWidth.width)<1,`Timeline fills the available card width at ${width}px`);
      const topLabel=await card.locator('.active-chart-scale span').first().boundingBox(), bottomLabel=await card.locator('.active-chart-scale span').last().boundingBox();
      assert.ok(topLabel.y+topLabel.height<=plot.y+1 && bottomLabel.y>=plot.y+plot.height-1,`Power labels remain legible outside the full-width plot at ${width}px`);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal page overflow');
    }
    // Even unusually large power readings must not truncate the y-axis label.
    await page.setViewportSize({width:320,height:900});
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;window.originalGraphPower=a.active_power_samples[0].watts;a.active_power_samples[0].watts=1234567;document.querySelector('motorvarmare-card').hass={...window.hass};});
    const largeLabel=card.locator('.active-chart-scale span').first();
    assert.match(await largeLabel.innerText(),/1\s?234\s?600 W/,'The full power value is displayed');
    const largeBox=await largeLabel.boundingBox(), chartBox=await card.locator('.active-chart').boundingBox();
    assert.ok(largeBox.x>=chartBox.x && largeBox.x+largeBox.width<=chartBox.x+chartBox.width,'Large power labels fit the card');
    await page.evaluate(()=>{window.hass.states['sensor.car'].attributes.active_power_samples[0].watts=window.originalGraphPower;document.querySelector('motorvarmare-card').hass={...window.hass};});
    await page.setViewportSize({width:390,height:900});
    await page.evaluate(()=>{window.hass.states['sensor.car'].attributes.active_power_samples.push({at:'2026-11-12T08:40:00Z',watts:999});document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.equal(await card.locator('.active-chart path').getAttribute('d'),graphPath,'A future sample is never drawn as observed power');
    await page.evaluate(()=>{window.hass.states['sensor.car'].attributes.active_measurement_started_at=null;document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.doesNotMatch(await card.locator('.active-metrics').innerText(),/0,35 kWh|1,20 SEK/,'Do not present an unbounded measurement period as a complete session');
    assert.match(await card.locator('.active-measurement-since').innerText(),/Mätningens starttid saknas/);
    await page.evaluate(()=>{window.hass.states['sensor.car'].attributes.active_measurement_started_at='2026-11-12T08:15:00Z';document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.match(await card.locator('.active-measurement-since').innerText(),/Mätning sedan 09:15/,'A resumed observation is labelled with its own start time');
    if (process.env.MV_PREVIEW_WIDTH) await page.setViewportSize({width:Number(process.env.MV_PREVIEW_WIDTH),height:900});
    if (process.env.MV_PREVIEW_PATH) await page.screenshot({path:process.env.MV_PREVIEW_PATH,fullPage:true});
    await card.locator('#extend-30').click();
    assert.deepEqual(await page.evaluate(()=>window.calls.shift()),{d:'button',s:'press',v:{entity_id:'button.extend'}});
    await page.evaluate(()=>{window.hass.states['sensor.car'].attributes.active_until='2026-11-12T09:30:00Z';document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.match(await card.locator('.active-remaining').innerText(),/1 tim 5 min kvar/);
    assert.deepEqual(await card.locator('.active-axis .active-tick').allInnerTexts(),['09:00','09:45','10:30'],'Extension updates the shared time axis');
    assert.match(await card.locator('.active-chart path').getAttribute('d'),/L17\.78 25\.00/,'Extension rescales the graph to the new stop time');
    await page.clock.fastForward(60000);
    assert.match(await card.locator('.active-remaining').innerText(),/1 tim 4 min kvar/,'Timer updates without HA state changes');
    // A failed/late switch-off must not hide measurements after the planned stop.
    await page.setViewportSize({width:390,height:300});
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.active_until='2026-11-12T08:26:15Z';a.active_power_samples.push({at:'2026-11-12T08:26:20Z',watts:999});document.querySelector('motorvarmare-card').hass={...window.hass}});
    const beforeLate=await card.locator('.active-chart path').getAttribute('d');
    await page.evaluate(()=>{window.scrollTo(0,300);document.querySelector('motorvarmare-card').shadowRoot.querySelector('#active-graph-toggle').focus({preventScroll:true});});
    const scrollBeforeLate=await page.evaluate(()=>window.scrollY);
    await page.clock.fastForward(60000);
    assert.match(await card.locator('.active-remaining').innerText(),/Stopptiden har passerat/);
    assert.notEqual(await card.locator('.active-chart path').getAttribute('d'),beforeLate,'The late observed power is shown when time advances without a Home Assistant update');
    assert.equal(await card.locator('.active-progress .active-stop-marker').isVisible(),true,'The planned stop is separately marked');
    assert.equal(await card.locator('.active-chart .active-stop-marker').isVisible(),true);
    const progressLate=await card.locator('.active-progress').boundingBox(), plotLate=await card.locator('.active-chart-plot').boundingBox();
    assert.ok(Math.abs(progressLate.x-plotLate.x)<1 && Math.abs(progressLate.width-plotLate.width)<1,'Both axes remain aligned after the planned stop');
    assert.equal(await page.evaluate(()=>window.scrollY),scrollBeforeLate,'Clock updates do not jump the page');
    assert.equal(await card.locator('#active-graph-toggle').evaluate(el=>el===el.getRootNode().activeElement),true,'Clock updates preserve keyboard focus');
    await page.evaluate(()=>{window.hass.states['sensor.car'].attributes.active_until='2026-11-12T09:30:00Z';document.querySelector('motorvarmare-card').hass={...window.hass}});
    await page.setViewportSize({width:390,height:900});
    await card.locator('#active-graph-toggle').click();
    assert.equal(await card.locator('.active-chart').count(),0);
    await page.evaluate(()=>{document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.equal(await card.locator('#active-graph-toggle').getAttribute('aria-expanded'),'false','Graph choice remains after HA updates');
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.active_max_until='2026-11-12T09:45:00Z';document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.match(await card.locator('#extend-30').innerText(),/Förläng till max/);
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.can_extend=false;a.active_until=a.active_max_until;document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.equal(await card.locator('#extend-30').isDisabled(),true);
    assert.match(await card.locator('.active-limit').innerText(),/Fyratimmarsgränsen är nådd/);
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.power_sensor_configured=false;a.energy_sensor_configured=false;document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.match(await card.locator('.active-no-sensor').innerText(),/Välj en effektsensor i integrationens inställningar/);
    assert.equal(await card.locator('.active-progress').count(),1,'Timeline works without power sensor');
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.active_started_at='2026-10-25T00:50:00Z';a.active_until='2026-10-25T01:20:00Z';document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.match(await card.locator('.active-times').innerText(),/02:50.*GMT\+2[\s\S]*02:20.*GMT\+1/,'Repeated autumn clock hours include their offsets');
    assert.match(await card.locator('.active-remaining').innerText(),/Stopptiden har passerat/,'Do not imply a heater has stopped when its planned stop is in the past');
    await page.clock.setSystemTime(new Date('2026-10-25T01:30:00Z'));
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.active_started_at='2026-10-25T00:10:00Z';a.active_until='2026-10-25T01:50:00Z';document.querySelector('motorvarmare-card').hass={...window.hass}});
    const dstTicks=await card.locator('.active-tick').allTextContents();
    assert.match(dstTicks[0],/02:10.*GMT\+2/);
    assert.match(dstTicks[1],/02:00.*GMT\+1/,'A clock that moves back within the interval gets an offset');
    assert.match(dstTicks[2],/02:50.*GMT\+1/);
    await page.clock.setSystemTime(new Date('2026-11-11T23:14:00Z'));
    await page.evaluate(()=>{const a=window.hass.states['sensor.car'].attributes;a.power_sensor_configured=true;a.active_started_at='2026-11-11T22:45:00Z';a.active_until='2026-11-11T23:15:00Z';a.active_power_samples=[{at:'2026-11-11T22:50:00Z',watts:600},{at:'2026-11-11T23:10:00Z',watts:700}];document.querySelector('motorvarmare-card').hass={...window.hass}});
    await card.locator('#active-graph-toggle').click();
    assert.deepEqual(await card.locator('.active-tick').allTextContents(),['23:45','00:00','00:15'],'The timeline crosses midnight in local time');
    assert.match(await card.locator('.active-times').innerText(),/11 nov.*23:45[\s\S]*00:15/,'Start and stop identify the correct local day');
    assert.match(await card.locator('.active-chart path').getAttribute('d'),/L266\.67 /,'Power on both sides of midnight shares the same actual elapsed axis');
    await page.evaluate(()=>{window.hass.language='en';window.hass.locale.language='en';document.querySelector('motorvarmare-card').hass={...window.hass}});
    assert.match(await card.locator('.active-header').innerText(),/Heating in progress/);
    assert.deepEqual(errors,[]);
    console.log('PASS: active timeline, power gaps, extension, missing sensors and translations');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1});
