/* Reproduce scrolling a Home Assistant dashboard during live state updates. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const browser = await chromium.launch({headless:true, executablePath:process.env.MOTORVARMARE_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
  try {
    const context = await browser.newContext({viewport:{width:390,height:700},isMobile:true,hasTouch:true,deviceScaleFactor:2});
    const page = await context.newPage();
    await page.setContent(`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="dashboard"><div id="before">Other dashboard cards</div><motorvarmare-card></motorvarmare-card><div id="after">More dashboard cards</div></div></body></html>`);
    await page.addStyleTag({content:`html,body{margin:0;height:100%;font-family:Arial,sans-serif}#dashboard{height:100dvh;overflow-y:auto;overscroll-behavior:contain}#before{height:450px}#after{height:900px}motorvarmare-card{display:block;margin:0 10px}ha-card{display:block}`});
    await page.evaluate(()=>{
      customElements.define('ha-card',class extends HTMLElement{});
      customElements.define('ha-icon',class extends HTMLElement{});
    });
    await page.addScriptTag({path:process.env.MOTORVARMARE_CARD_PATH || path.join(__dirname,'..','..','custom_components','motorvarmare','www','ha-motorvarmare-card.js')});
    await page.evaluate(()=>{
      const controls={manual_departure:'datetime.car_manual',clear_departure:'button.car_clear',heater_switch:'switch.car_heater',calendar:'calendar.car_schedule',start_now:'button.car_start',stop_now:'button.car_stop',weekly_times:Array.from({length:7},(_,i)=>`time.car_${i}`),weekly_enabled:Array.from({length:7},(_,i)=>`switch.car_${i}`)};
      const attrs={friendly_name:'Bil 1 Status',control_entities:controls,temperature:1,current_duration_minutes:60,owned:false,schedule_7_days:[],history:[]};
      const states={'sensor.car_status':{entity_id:'sensor.car_status',state:'waiting_to_start',attributes:attrs},'switch.car_heater':{entity_id:'switch.car_heater',state:'off',attributes:{}},'sensor.other':{entity_id:'sensor.other',state:'0',attributes:{}}};
      for(const [id,state] of [[controls.manual_departure,'unknown'],[controls.clear_departure,'unknown'],[controls.start_now,'unknown'],[controls.stop_now,'unknown'],[controls.calendar,'off']]) states[id]={entity_id:id,state,attributes:{}};
      controls.weekly_times.forEach(id=>states[id]={entity_id:id,state:'07:00:00',attributes:{}});
      controls.weekly_enabled.forEach(id=>states[id]={entity_id:id,state:'off',attributes:{}});
      window.calls=[];
      window.baseHass={states,language:'sv',locale:{language:'sv'},config:{time_zone:'Europe/Stockholm'},async callService(domain,service,data){window.calls.push({domain,service,data});},async callWS(){return {events:[]};}};
      const card=document.querySelector('motorvarmare-card');card.setConfig({status_entity:'sensor.car_status'});card.hass=window.baseHass;
    });
    const card=page.locator('motorvarmare-card'), dashboard=page.locator('#dashboard');
    await card.locator('[data-main-tab="settings"]').click();
    await card.locator('#week').click();
    await card.locator('[data-main-tab="energy"]').click();
    await card.locator('#history-toggle').click();
    await card.locator('[data-main-tab="calendar"]').click();
    await page.evaluate(()=>{const root=document.querySelector('motorvarmare-card').shadowRoot;window.anchorNodes={card:root.querySelector('ha-card'),calendar:root.querySelector('.calendar'),week:root.querySelector('#week'),history:root.querySelector('#history-toggle')};});
    for (const relative of [0.25,0.55,0.85]) {
      const before=await dashboard.evaluate((root,ratio)=>{const card=root.querySelector('motorvarmare-card');root.scrollTop=card.offsetTop+card.offsetHeight*ratio;return root.scrollTop;},relative);
      for(let i=0;i<8;i++) {
        await page.evaluate((n)=>{const h=window.baseHass;const id='sensor.other';const states={...h.states,[id]:{...h.states[id],state:String(n)}};document.querySelector('motorvarmare-card').hass={...h,states};},i);
        await page.waitForTimeout(16);
      }
      const after=await dashboard.evaluate(root=>root.scrollTop);
      assert.ok(Math.abs(after-before)<3,`Dashboard scroll changed after unrelated hass updates: ${before} -> ${after}`);
      assert.ok(await page.evaluate(()=>{const root=document.querySelector('motorvarmare-card').shadowRoot;return window.anchorNodes.card===root.querySelector('ha-card') && window.anchorNodes.calendar===root.querySelector('.calendar') && window.anchorNodes.week===root.querySelector('#week') && window.anchorNodes.history===root.querySelector('#history-toggle');}),'Unrelated HA updates must preserve existing elements that can be browser scroll anchors');
      for (let i=0;i<8;i++) {
        await page.evaluate(n=>{const h=window.baseHass;const id='sensor.car_status';const s=h.states[id];const states={...h.states,[id]:{...s,attributes:{...s.attributes,temperature:2.5+n/10}}};document.querySelector('motorvarmare-card').hass={...h,states};},i);
        await page.waitForTimeout(16);
      }
      const changed=await dashboard.evaluate(root=>root.scrollTop);
      assert.ok(Math.abs(changed-before)<3,`Dashboard scroll changed after temperature update: ${before} -> ${changed}`);
      assert.match(await card.locator('.wrap').innerText(),/3,2/,'Real sensor updates must still be visible');
      assert.ok(await page.evaluate(()=>{const root=document.querySelector('motorvarmare-card').shadowRoot;return window.anchorNodes.card===root.querySelector('ha-card') && window.anchorNodes.calendar===root.querySelector('.calendar') && window.anchorNodes.week===root.querySelector('#week') && window.anchorNodes.history===root.querySelector('#history-toggle');}),'Temperature updates must preserve existing elements that can be browser scroll anchors');
    }
    // Some dashboards scroll the document itself rather than a nested view.
    await page.addStyleTag({content:'html,body{height:auto;min-height:100%}#dashboard{height:auto;overflow:visible}'});
    await page.evaluate(()=>window.scrollTo(0,document.querySelector('motorvarmare-card').offsetTop+400));
    const beforeWindow=await page.evaluate(()=>window.scrollY);
    for (let i=0;i<8;i++) {
      await page.evaluate(n=>{const h=window.baseHass;const id='sensor.car_status';const s=h.states[id];const states={...h.states,[id]:{...s,attributes:{...s.attributes,temperature:4+n/10}}};document.querySelector('motorvarmare-card').hass={...h,states};},i);
      await page.waitForTimeout(16);
    }
    const afterWindow=await page.evaluate(()=>window.scrollY);
    assert.ok(Math.abs(afterWindow-beforeWindow)<3,`Window scroll changed after temperature updates: ${beforeWindow} -> ${afterWindow}`);
    assert.match(await card.locator('.wrap').innerText(),/4,7/);
    // A notice appearing before the calendar must not disconnect or move the
    // calendar anchor, including when the notice disappears again.
    await page.evaluate(()=>{const root=document.querySelector('motorvarmare-card').shadowRoot;const target=root.querySelector('.calendar');window.noticeAnchor=target;window.reinserted=[];window.noticeObserver=new MutationObserver(records=>{for(const r of records) for(const n of r.removedNodes) if(n===target || (n.contains && n.contains(target))) window.reinserted.push({tag:n.nodeName,className:n.className||'',id:n.id||''});});window.noticeObserver.observe(root,{childList:true,subtree:true});window.scrollBy(0,target.getBoundingClientRect().top-140);});
    for (const message of ['Tillfälligt fel',null]) {
      const priorTop=await card.locator('.calendar').evaluate(el=>el.getBoundingClientRect().top);
      await page.evaluate(error=>{const h=window.baseHass;const id='sensor.car_status';const s=h.states[id];const states={...h.states,[id]:{...s,attributes:{...s.attributes,error}}};document.querySelector('motorvarmare-card').hass={...h,states};},message);
      await page.waitForTimeout(30);
      const anchor=await page.evaluate(()=>({same:window.noticeAnchor===document.querySelector('motorvarmare-card').shadowRoot.querySelector('.calendar'),reinserted:window.reinserted}));
      assert.ok(anchor.same && anchor.reinserted.length===0,`Calendar anchor was removed or reinserted when notice=${message}: ${JSON.stringify(anchor)}`);
      const afterTop=await card.locator('.calendar').evaluate(el=>el.getBoundingClientRect().top);
      // The notice takes up space, so ordinary reflow can move the calendar
      // by its height. It must not cause a large jump to the page top.
      assert.ok(Math.abs(afterTop-priorTop)<55,`Calendar jumped in viewport after notice changed: ${priorTop} -> ${afterTop}`);
    }
    await page.evaluate(()=>window.noticeObserver.disconnect());
    // In-progress settings must survive updates even after the input loses
    // focus: the live DOM properties of inputs/selects differ from attributes.
    await card.locator('.mobile-add').click();
    await card.locator('#calendar-time').fill('09:25');
    await card.locator('#repeat-frequency').focus();
    await card.locator('#repeat-frequency').selectOption('WEEKLY');
    await card.locator('#repeat-interval').fill('3');
    await card.locator('[data-repeat-day="TU"]').check();
    await card.locator('#repeat-interval').blur();
    await page.waitForTimeout(20);
    const editorBefore=await page.evaluate(()=>{const root=document.querySelector('motorvarmare-card').shadowRoot;window.editorNodes={select:root.querySelector('#repeat-frequency'),checkbox:root.querySelector('[data-repeat-day="TU"]'),interval:root.querySelector('#repeat-interval')};return true;});
    assert.ok(editorBefore);
    for (let i=0;i<3;i++) {
      await page.evaluate(n=>{const h=window.baseHass;const id='sensor.car_status';const s=h.states[id];const states={...h.states,[id]:{...s,attributes:{...s.attributes,temperature:6+n/10}}};document.querySelector('motorvarmare-card').hass={...h,states};},i);
      await page.waitForTimeout(16);
    }
    assert.equal(await card.locator('#calendar-time').inputValue(),'09:25');
    assert.equal(await card.locator('#repeat-frequency').inputValue(),'WEEKLY');
    assert.equal(await card.locator('#repeat-interval').inputValue(),'3');
    assert.equal(await card.locator('[data-repeat-day="TU"]').isChecked(),true);
    assert.ok(await page.evaluate(()=>{const r=document.querySelector('motorvarmare-card').shadowRoot;return window.editorNodes.select===r.querySelector('#repeat-frequency') && window.editorNodes.checkbox===r.querySelector('[data-repeat-day="TU"]') && window.editorNodes.interval===r.querySelector('#repeat-interval');}),'Draft form elements should remain connected during unrelated live updates');
    await card.locator('#cancel-calendar').click();
    await page.evaluate(()=>{window.calls=[];});
    await card.locator('#start-now').click();
    assert.equal(await page.evaluate(()=>window.calls.length),1,'One tap after several HA updates must call the start service exactly once');
    assert.deepEqual(await page.evaluate(()=>window.calls[0]),{domain:'button',service:'press',data:{entity_id:'button.car_start'}});
    console.log('PASS: dashboard page scroll survives repeated unrelated and relevant updates on mobile');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
