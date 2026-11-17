/* Practical small-screen and keyboard regressions for the dashboard card. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:320,height:700}, isMobile:true, hasTouch:true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="before">Dashboard</div><motorvarmare-card></motorvarmare-card><div id="after">More cards</div></body></html>');
    await page.addStyleTag({content:'html,body{margin:0;font-family:Arial,sans-serif}#before,#after{height:450px}motorvarmare-card,ha-card{display:block}motorvarmare-card{margin:0 8px}'});
    await page.evaluate(()=>{customElements.define('ha-card',class extends HTMLElement{});customElements.define('ha-icon',class extends HTMLElement{});});
    await page.addScriptTag({path:path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const control_entities={heater_switch:'switch.heater',calendar:'calendar.car',start_now:'button.start',stop_now:'button.stop',manual_departure:'datetime.manual',clear_departure:'button.clear',weekly_times:[],weekly_enabled:[]};
      const attributes={friendly_name:'Bil',control_entities,temperature:-5,current_duration_minutes:90,schedule_query_supported:true,schedule_7_days:[],heating_history:[]};
      const states={'sensor.status':{entity_id:'sensor.status',state:'waiting_to_start',attributes},'switch.heater':{state:'off',attributes:{}},'calendar.car':{state:'off',attributes:{}},'button.start':{state:'unknown',attributes:{}},'button.stop':{state:'unknown',attributes:{}},'datetime.manual':{state:'unknown',attributes:{}},'button.clear':{state:'unknown',attributes:{}}};
      window.calls=[];
      window.hass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(domain,service,data){window.calls.push({domain,service,data});},async callWS(){return {events:[],calendar_error:false};}};
      const card=document.querySelector('motorvarmare-card');card.setConfig({status_entity:'sensor.status'});card.hass=window.hass;
    });
    const card=page.locator('motorvarmare-card');
    // The main heater action is reachable and operable via a keyboard.
    const start=card.locator('#start-now');
    assert.equal(await start.isVisible(),true);
    assert.match((await start.innerText()).trim(),/starta/i);
    // Use Tab, rather than programmatic focus, so a control removed from the
    // normal tab order cannot pass the test.
    let foundStart=false;
    for (let i=0;i<40;i++) {
      await page.keyboard.press('Tab');
      if (await start.evaluate(el=>el.getRootNode().activeElement===el)) { foundStart=true; break; }
    }
    assert.equal(foundStart,true,'Start must be reachable using Tab');
    assert.equal(await page.evaluate(()=>window.calls.length),0,'Focusing a control must not start the heater');
    await page.keyboard.press('Enter');
    assert.deepEqual(await page.evaluate(()=>window.calls),[{domain:'button',service:'press',data:{entity_id:'button.start'}}]);

    // Every visible, enabled button needs a name; icons alone are not enough.
    for (const view of ['calendar','energy','settings']) {
      await card.locator(`[data-main-tab="${view}"]`).click();
      const unnamed = await card.evaluate(host=>Array.from(host.shadowRoot.querySelectorAll('button'))
        .filter(el=>!el.disabled && el.getClientRects().length && getComputedStyle(el).visibility!=='hidden')
        .filter(el=>!(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.innerText.trim() || el.getAttribute('title')))
        .map(el=>el.outerHTML));
      assert.deepEqual(unnamed,[],`Visible buttons on ${view} must have accessible names`);
      assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),`${view} must fit on a 320px screen`);
    }
    // The departure editor must label its actual input controls, including
    // the options revealed by recurring schedules.
    await card.locator('[data-main-tab="calendar"]').click();
    await card.locator('#new-departure').click();
    if (await card.locator('#repeat-frequency').count()) await card.locator('#repeat-frequency').selectOption('WEEKLY');
    const unnamedFields=await card.evaluate(host=>Array.from(host.shadowRoot.querySelectorAll('input,select,textarea'))
      .filter(el=>!el.disabled && el.getClientRects().length && getComputedStyle(el).visibility!=='hidden')
      .filter(el=>!(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.labels?.length))
      .map(el=>el.outerHTML));
    assert.deepEqual(unnamedFields,[],'Departure form controls must have accessible labels');
    await card.locator('#cancel-calendar').click();

    // Growing text and switching between portrait and landscape must not make
    // the dashboard itself horizontally scrollable.
    await page.addStyleTag({content:'html{font-size:150%}'});
    for (const width of [320, 390, 700]) {
      await page.setViewportSize({width,height:700});
      for (const view of ['calendar','energy','settings']) {
        await card.locator(`[data-main-tab="${view}"]`).click();
        assert.ok(await card.evaluate(el=>el.scrollWidth<=el.clientWidth+1),`${view} must fit at width ${width} with larger text`);
      }
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: keyboard heater action, named controls and narrow-screen layouts');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exit(1)});
