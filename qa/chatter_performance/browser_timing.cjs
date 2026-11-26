const {chromium} = require('playwright');
const fs = require('fs');
const crypto = require('crypto');
const {parseArgs} = require('util');
process.umask(0o077);
const {values} = parseArgs({options:{fixture:{type:'string'},output:{type:'string'},origin:{type:'string',default:'http://127.0.0.1:5085'},gateway:{type:'string',default:'http://127.0.0.1:5087'},chrome:{type:'string'},agents:{type:'string',default:'10'},incoming:{type:'string',default:'30'},replies:{type:'string',default:'30'},disableWebsocket:{type:'boolean',default:false}}});
for (const origin of [values.origin,values.gateway]) if (new URL(origin).hostname !== '127.0.0.1' || !/^50[0-9]{2}$/.test(new URL(origin).port)) throw new Error('Use local alternate test ports');
for (const key of ['agents','incoming','replies']) if (!Number.isInteger(Number(values[key])) || Number(values[key]) < (key==='agents' ? 1 : 0) || Number(values[key]) > (key==='agents' ? 10 : 30)) throw new Error('Use bounded synthetic sample counts');
if (!values.fixture || !values.output || !values.chrome) throw new Error('Supply private fixture, output and Chrome executable paths');
(async () => {
 const fixture = JSON.parse(fs.readFileSync(values.fixture,'utf8'));
 if (!fixture.database?.startsWith('callcenter_timing_')) throw new Error('A disposable timing fixture is required');
 const eventBase = Date.now();
 const browser = await chromium.launch({executablePath:values.chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-background-timer-throttling','--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding']});
 const pages = [];
 const requests = [];
 const cpuStarted = process.cpuUsage();
 const consoleErrors = [];
 try {
  for (const [index, agent] of fixture.agents.slice(0,Number(values.agents)).entries()) {
   const context = await browser.newContext({baseURL:values.origin});
   if (values.disableWebsocket) await context.routeWebSocket(url => url.pathname === '/websocket', socket => socket.close({code:1000,reason:'Synthetic offline test'}));
   const response = await context.request.post('/web/session/authenticate', {data:{jsonrpc:'2.0',method:'call',params:{db:fixture.database,login:agent.login,password:fixture.password}}});
   if (!(await response.json()).result?.uid) throw new Error('Synthetic agent login failed');
   const page = await context.newPage();
   page.on('response', async response => {
    if (response.url().includes('/web/dataset/call_kw/ab_crm_')) {
     try { requests.push({route:new URL(response.url()).pathname, response_bytes:(await response.body()).length}); } catch {}
    }
   });
   page.on('pageerror', error => consoleErrors.push({agent:index,error:error.name}));
   await page.goto('/odoo?debug=assets');
   await page.waitForFunction(() => Boolean(odoo.__WOWL_DEBUG__?.root?.env), {timeout:60000});
   await page.evaluate(async ({session, conversation}) => {
    window.timingEvents = [];
    sessionStorage.setItem('ab_chatter_timing','1');
    window.addEventListener('ab-chatter-timing', event => window.timingEvents.push(event.detail));
    const env = odoo.__WOWL_DEBUG__.root.env;
    env.services.ab_chatter_session.set(session);
    await env.services.action.doAction('ab_crm_sales_workspace.action_workspace', {additionalContext:{chatter_conversation_id:conversation}});
   }, {session:agent.session,conversation:fixture.conversation_id});
   await page.waitForSelector('.ab_message[data-message-id]', {timeout:60000});
   if (values.disableWebsocket) await page.evaluate(() => odoo.__WOWL_DEBUG__.root.env.services.bus_service.stop());
   pages.push(page);
   console.log('Agent ready',index);
  }
  const samples = [];
  const replies = [];
  const save = () => fs.writeFileSync(values.output,JSON.stringify({state:'running',agents:pages.length,samples,replies,console_errors:consoleErrors},null,2));
  for (let index=0;index<Number(values.incoming);index++) {
   const messageId = eventBase + index;
   const reference = `12345:${messageId}`;
   const correlation = crypto.createHash('sha256').update(JSON.stringify(['workspace-bot', reference]).replaceAll(',', ', ')).digest('hex').slice(0,32);
   const started = Date.now();
   const response = await fetch(values.gateway + '/webhooks/telegram/workspace-bot', {method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Bot-Api-Secret-Token':fixture.webhook_secret},body:JSON.stringify({update_id:messageId,message:{message_id:messageId,chat:{id:12345,type:'private'},date:Math.floor(Date.now()/1000),text:`Synthetic timing ${index}`}})});
   if (!response.ok) throw new Error('Synthetic webhook rejected');
   const durableAck=Date.now();
   await Promise.all(pages.map(page => page.waitForFunction(correlation => window.timingEvents.some(event => event.stage==='rendered' && event.correlation_id===correlation),correlation,{timeout:30000})));
   const agentSamples = await Promise.all(pages.map(page => page.evaluate(correlation => window.timingEvents.filter(event => event.correlation_id===correlation),correlation)));
   if (values.disableWebsocket && agentSamples.flat().some(event => event.stage==='browser_notification')) throw new Error('The offline fixture received a websocket notification');
   samples.push({correlation_id:correlation,reception_ms:started,durable_ack_ms:durableAck,agents:agentSamples});
   save();
   console.log('Measured synthetic message', index);


  }
  for (let index=0;index<Number(values.replies);index++) {
   const previous = await pages[0].evaluate(() => window.timingEvents.filter(event => event.stage==='queued_ack_rendered').length);
   await pages[0].locator('.ab_composer_input').fill(`Synthetic outgoing timing ${index}`);
   await pages[0].locator('.ab_composer_input').press('Enter');
   await pages[0].waitForFunction(previous => window.timingEvents.filter(event => event.stage==='queued_ack_rendered').length > previous, previous, {timeout:30000});
   replies.push(await pages[0].evaluate(() => {
    const queued = window.timingEvents.filter(event => event.stage==='queued_ack_rendered').at(-1);
    const submitted = window.timingEvents.find(event => event.stage==='reply_submission' && event.correlation_id===queued.correlation_id);
    return {correlation_id:queued.correlation_id, submission_ms:submitted.timestamp_ms, queued_ack_ms:queued.timestamp_ms};
   }));
   await pages[0].waitForFunction(() => !document.querySelector('.ab_composer fieldset')?.disabled);
   save();
   console.log('Measured synthetic queued reply',index);
  }
  fs.writeFileSync(values.output,JSON.stringify({state:'completed',agents:pages.length,samples,replies,requests,node_cpu_microseconds:process.cpuUsage(cpuStarted),node_rss_bytes:process.memoryUsage().rss,console_errors:consoleErrors},null,2));
 } finally {await browser.close();}
})().catch(error => {console.error(error);process.exit(1);});
