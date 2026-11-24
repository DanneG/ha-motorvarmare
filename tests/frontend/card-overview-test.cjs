const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:390,height:740},isMobile:true,hasTouch:true});
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.setContent('<!doctype html><html><body></body></html>');
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{});
      customElements.define('ha-icon',class extends HTMLElement{});
    });
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const make=(name, state, next, temp) => ({entity_id:`sensor.${name}_status`,state,
        attributes:{friendly_name:`${name} status`, next_departure:next,temperature:temp,
          control_entities:{heater_switch:`switch.${name}_heater`},schedule_7_days:[]}});
      window.hass={language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},states:{
        'sensor.sivan_status':make('sivan','waiting_to_start','2026-11-07T06:00:00Z',-5),
        'sensor.eka_status':make('eka','heating','2026-11-07T08:00:00Z',0),
        'sensor.outside':{entity_id:'sensor.outside',state:'-5',attributes:{}},
        'switch.sivan_heater':{entity_id:'switch.sivan_heater',state:'off',attributes:{}},
        'switch.eka_heater':{entity_id:'switch.eka_heater',state:'on',attributes:{}}
      },async callService(){},async callWS(){return {events:[]}}};
      const card=document.createElement('motorvarmare-overview');
      card.setConfig({entities:['sensor.sivan_status','sensor.eka_status']}); card.hass=window.hass;
      document.body.appendChild(card);
    });
    const overview=page.locator('motorvarmare-overview');
    assert.equal(await overview.locator('.car').count(),2);
    assert.match(await overview.locator('.wrap').innerText(),/sivan status/);
    assert.match(await overview.locator('.wrap').innerText(),/Väntar på start/);
    assert.match(await overview.locator('.wrap').innerText(),/Värmer/);
    assert.match(await overview.locator('[data-entity="sensor.sivan_status"]').innerText(),/07:00/,'Uses HA timezone');
    await page.evaluate(()=>{
      const overview=document.querySelector('motorvarmare-overview');
      const top=document.createElement('div'), bottom=document.createElement('div');
      top.style.height=bottom.style.height='1200px';
      document.body.insertBefore(top,overview);document.body.appendChild(bottom);
      window.scrollTo(0,overview.offsetTop+20);
      window.overviewScroll=window.scrollY;
      const attrs=window.hass.states['sensor.sivan_status'].attributes;
      attrs.alarm_active=true;attrs.energy_monitor_status='low_power';
      attrs.operational_problems=['temperature_stale'];overview.hass={...window.hass};
    });
    assert.match(await overview.locator('[data-entity="sensor.sivan_status"]').innerText(),/kabeln/i,'Low-power cable warning must be visible in the overview');
    assert.match(await overview.locator('[data-entity="sensor.sivan_status"]').innerText(),/Temperaturvärdet kan vara inaktuellt/,'Operational warnings must be visible in the overview');
    assert.ok(await page.evaluate(()=>Math.abs(window.scrollY-window.overviewScroll)<3),'Live warnings must not jump the dashboard to the top');
    await page.evaluate(()=>{window.beforeOverviewNode=document.querySelector('motorvarmare-overview').shadowRoot.querySelector('.car');
      window.hass.states['sensor.sivan_status'].attributes.temperature=-8;
      document.querySelector('motorvarmare-overview').hass={...window.hass};});
    assert.equal(await page.evaluate(()=>window.beforeOverviewNode===document.querySelector('motorvarmare-overview').shadowRoot.querySelector('.car')),true,'Hass updates preserve scroll anchors');
    assert.match(await overview.locator('[data-entity="sensor.sivan_status"]').innerText(),/−?8|−8|-8/);
    await overview.locator('[data-entity="sensor.sivan_status"]').click();
    assert.equal(await overview.locator('motorvarmare-card').count(),1);
    assert.equal(await overview.locator('motorvarmare-card').evaluate(el=>el._config.status_entity),'sensor.sivan_status');
    await page.evaluate(()=>{const detail=document.querySelector('motorvarmare-overview').shadowRoot.querySelector('motorvarmare-card');window.previousDetail=detail;detail._draft='unsaved';window.hass.states['sensor.sivan_status'].attributes.temperature=-9;document.querySelector('motorvarmare-overview').hass={...window.hass};});
    assert.equal(await page.evaluate(()=>window.previousDetail===document.querySelector('motorvarmare-overview').shadowRoot.querySelector('motorvarmare-card')),true,'Open detail survives HA updates');
    assert.equal(await overview.locator('motorvarmare-card').evaluate(el=>el._draft),'unsaved');
    await overview.locator('#overview-back').click();
    assert.equal(await overview.locator('.car').count(),2);
    await page.evaluate(()=>{window.hass.language='en';window.hass.locale.language='en';window.hass.states['sensor.eka_status'].state='unavailable';document.querySelector('motorvarmare-overview').hass={...window.hass};});
    assert.match(await overview.locator('.wrap').innerText(),/Engine heaters/);
    assert.match(await overview.locator('.wrap').innerText(),/Status unavailable/);
    assert.match(await overview.locator('[data-entity="sensor.sivan_status"]').innerText(),/temperature reading may be out of date/i,'Operational warning is translated');
    assert.match(await overview.locator('[data-entity="sensor.sivan_status"]').innerText(),/heater cable is plugged in/i,'Cable warning is translated');
    assert.ok(await page.evaluate(()=>window.customCards.some(card=>card.type==='motorvarmare-overview')));
    await page.evaluate(()=>{
      const editor=document.createElement('motorvarmare-overview-editor');
      editor.setConfig({entities:['sensor.sivan_status','sensor.missing_status']});
      editor.hass=window.hass;window.configEvents=[];
      editor.addEventListener('config-changed',event=>window.configEvents.push(event.detail.config));
      document.body.appendChild(editor);
    });
    const editor=page.locator('motorvarmare-overview-editor');
    assert.equal(await editor.locator('[data-entity]').count(),3,'Offers cars and preserves missing selected entries');
    assert.equal(await editor.locator('[data-entity="sensor.outside"]').count(),0,'Ordinary temperature sensor is not offered');
    await editor.locator('[data-entity="sensor.eka_status"]').check();
    const config=await page.evaluate(()=>window.configEvents.at(-1));
    assert.deepEqual([...config.entities].sort(),['sensor.eka_status','sensor.missing_status','sensor.sivan_status']);
    await editor.locator('#title').fill('Both cars'); await editor.locator('#title').dispatchEvent('change');
    assert.equal((await page.evaluate(()=>window.configEvents.at(-1))).title,'Both cars');
    assert.deepEqual(errors,[]);
    console.log('PASS: multi-car overview, details, editor, locale, unavailable sensors and scroll anchors');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exit(1)});
