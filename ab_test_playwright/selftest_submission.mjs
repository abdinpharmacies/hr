import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const { chromium } = createRequire('/opt/playwright/package.json')('playwright');
import { readFileSync } from 'node:fs';
import { submitOnce, assertSavedInvoice } from './submission.mjs';
const browser = await chromium.launch({headless:true});
try {
 for (const scenario of ['saved','rejected','pending','lost_response','timeout']) {
  const context = await browser.newContext();
  const page = await context.newPage();
  let requests=0, polls=0;
  await page.route('http://test.invalid/**', async route => {
   if (route.request().url().endsWith('/pos_submit')) {
    requests++;
    if (scenario === 'lost_response' || scenario === 'timeout') return route.abort();
    return route.fulfill({json: scenario==='rejected' ? {error:{data:{message:'Simulated validation rejection'}}} : {result:{id:123,status:scenario}}});
   }
   return route.fulfill({contentType:'text/html',body:`<div class="o_ab_sales_pos_submit_dialog"><button onclick="fetch('/web/dataset/call_kw/ab_sales_pos_api/pos_submit', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({params:{kwargs:{header:{pos_client_token:'test-token'}}}})}).catch(()=>{})">Submit (F10)</button></div>`});
  });
  await page.goto('http://test.invalid/');
  const result={submission:'NOT_EXECUTED'};
  const rpc=async(model,method,args,kwargs)=>{
   assert.equal(method,'pos_submission_status'); assert.deepEqual(kwargs.tokens,['test-token']); polls++;
   if (scenario==='timeout'||scenario==='rejected') return {};
   if (requests===0) return {};
   return {'test-token':{id:123,status:scenario==='pending'?'pending':'saved',eplus_serial:456}};
  };
  let error;
  try {await submitOnce({page,rpc,token:'test-token',result,timeoutMs:500,pollMs:10});} catch(e){error=e;}
  assert.equal(requests,1,scenario+' must click exactly once');
  assert.ok(polls>0);
  if (['saved','lost_response'].includes(scenario)) {assert.equal(error,undefined);assert.equal(result.submission,'SAVED');assert.equal(result.invoice_id,123);}
  else {assert.ok(error);assert.equal(result.submission,scenario==='timeout'?'UNKNOWN':scenario.toUpperCase());}
  await assert.rejects(()=>submitOnce({page,rpc,token:'test-token',result,timeoutMs:20}),/already attempted/);
  assert.equal(requests,1);
  console.log('PASS simulated '+scenario);
  await context.close();
 }
 const suite=JSON.parse(readFileSync(new URL('./sales_ui_cases.json', import.meta.url)));
 const test=suite.cases[0];
 const header={id:123,pos_client_token:'test-token',status:'saved',store_id:[104,'store'],customer_id:[19934,'customer'],employee_id:[668,'employee'],contract_id:false,applied_program_ids:[],total_price:380,total_net_amount:380,promo_discount_amount:0,line_ids:[1,2]};
 const lines=test.lines.map(l=>({product_id:[l.product_id,'product'],qty:l.qty,sell_price:suite.records.products.find(p=>p.id===l.product_id).unit_price,uom_id:[1,'unit'],unavailable_reason:false,unavailable_reason_other:false}));
 const result={submission:'SAVED',invoice_id:123,client_token:'test-token',checkpoints:[]};
 const rpc=async(model,method,args)=>{assert.equal(method,'read');return model==='ab_sales_header'?[header]:lines;};
 await assertSavedInvoice({rpc,suite,test,result});
 assert.deepEqual(result.checkpoints,['saved_invoice']);
 for (const [field,value] of [['store_id',[999,'wrong']],['total_net_amount',999],['pos_client_token','wrong'],['applied_program_ids',[2]]]) {
  const original=header[field]; header[field]=value;
  await assert.rejects(()=>assertSavedInvoice({rpc,suite,test,result})); header[field]=original;
 }
 lines[0].qty=99; await assert.rejects(()=>assertSavedInvoice({rpc,suite,test,result}));lines[0].qty=1;
 await assert.rejects(()=>assertSavedInvoice({rpc,suite,test,result,shortages:{74542:true}}),/shortage reason/);
 console.log('PASS saved header, lines, totals and mismatch detection');
 const registry=JSON.parse(readFileSync(new URL('./actions.json', import.meta.url))).actions;
 const source=readFileSync(new URL('./sales_ui_runner.mjs', import.meta.url),'utf8');
 assert.deepEqual([...source.matchAll(/case '([^']+)'/g)].map(m=>m[1]),registry);
 console.log('PASS registered actions match runner handlers');
} finally {await browser.close();}
