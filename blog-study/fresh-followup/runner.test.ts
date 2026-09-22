import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { CONFIG, DEADLINE, instruction, confidenceInstruction, probability, budgetCheck, deadline, makeSchedule, validateCases, validateEndpoint, reserve, accounted, accepted, safety, validateIdentity, exclusive, locked, audit, executePath, sdk } from './runner.ts';
const item = {id:'a',text:'request',expected:'card_arrival',pathOrder:['cascade','gemini']};
async function temporary(fn:(d:string)=>Promise<void>) { const d = await mkdtemp(join(tmpdir(),'fresh-runner-test-')); try { await fn(d); } finally { await rm(d,{recursive:true,force:true}); } }
const endpoint = (m = CONFIG[0] as typeof CONFIG[number]) => ({tag:m.tag,provider_name:m.provider,model_id:m.model,name:`${m.provider} | ${m.version}`,status:0,context_length:100000,max_completion_tokens:65536,supported_parameters:['structured_outputs','response_format','temperature','max_tokens','reasoning','reasoning_effort'],pricing:{prompt:'0.00000075',completion:m.key==='jev'?'0':'0.00000375'}});
test('original prompt strings unchanged',async()=>{
 const original = await readFile(new URL('../../blog-study.ts',import.meta.url),'utf8');
 assert.ok(original.includes("const instruction = '"+instruction+"'")); assert.ok(original.includes("const confidenceInstruction = '"+confidenceInstruction+"'"));
});
test('validates cases, deterministic paired randomized schedule and separate OOS',()=>{
 assert.deepEqual(validateCases([item]),[item]); assert.throws(()=>validateCases([item,item]));
 const a = makeSchedule([item,{...item,id:'b'}],[item]); assert.equal(a.length,6); assert.equal(new Set(a.map(x=>x.key)).size,6);
 assert.deepEqual(a,makeSchedule([item,{...item,id:'b'}],[item])); assert.equal(a.filter(x=>x.path==='baseline').length,3);
});
test('actual frozen inputs support null OOS gold and preserve every recorded path order',async()=>{
 const bank=validateCases(JSON.parse(await readFile(new URL('./cases.json',import.meta.url),'utf8')));
 const oos=validateCases(JSON.parse(await readFile(new URL('./oos.json',import.meta.url),'utf8')));
 const schedule=makeSchedule(bank,oos);
 assert.equal(schedule.length,1200);
 const all=[...bank,...oos];
 for(let i=0;i<all.length;i++) {
  const pair=schedule.slice(i*2,i*2+2);
  assert.ok(pair.every(x=>x.item.id===all[i]!.id));
  assert.deepEqual(pair.map(x=>x.path),all[i]!.pathOrder!.map(x=>x==='gemini'?'baseline':x));
 }
 assert.ok(schedule.slice(0,1000).every(x=>x.cohort==='cases'));
 assert.ok(schedule.slice(1000).every(x=>x.cohort==='oos' && x.item.expected===null));
});
test('probabilities, deadline, and budget fail closed',()=>{
 for (const n of [NaN,-1,1.1,undefined,'1']) assert.throws(()=>probability(n));
 assert.equal(probability(1),1); deadline(DEADLINE-1); assert.throws(()=>deadline(DEADLINE));
 budgetCheck(0,.1); for(const args of [[8.89,.02],[0,0],[NaN,.1],[-1,.1]]) assert.throws(()=>budgetCheck(args[0]!,args[1]!));
 assert.equal(accounted({},.3),.3); assert.equal(accounted({estimatedCostUsd:0},.3),.3); assert.equal(accounted({billedCostUsd:.1},.3),.1);
});
test('pinned capability/provider/version and conservative reservation',()=>{
 for (const m of CONFIG) { const ep=endpoint(m); validateEndpoint(m,ep); const r=reserve(m,ep,{text:'x'}); assert.ok(r.amount>0); assert.equal(r.outputBound,65536); }
 assert.throws(()=>validateEndpoint(CONFIG[0],{...endpoint(),provider_name:'Other'}));
 assert.throws(()=>validateEndpoint(CONFIG[1],{...endpoint(CONFIG[1]),supported_parameters:[]}));
 assert.throws(()=>validateEndpoint(CONFIG[0],{...endpoint(),pricing:{prompt:'',completion:'0'}}));
 assert.throws(()=>validateEndpoint(CONFIG[0],{...endpoint(),pricing:{prompt:'1',completion:'1'}}));
 validateIdentity(CONFIG[1],{provider:CONFIG[1].provider,model:CONFIG[1].model});
 assert.throws(()=>validateIdentity(CONFIG[0],{model:CONFIG[0].version}));
 assert.throws(()=>validateIdentity(CONFIG[1],{provider:CONFIG[1].provider,model:'another-version'}));
});
test('real cascade sequential, threshold equality, fallback independent baseline and safety gates',async()=>{
 let active=0; const calls:string[]=[];
 const call=async(m:typeof CONFIG[number])=>{assert.equal(active++,0); calls.push(m.key); await new Promise(r=>setTimeout(r,2)); active--; return {status:'ok',nativeConfidence:.99,probability:.94};};
 const r=await executePath('cascade',call); assert.deepEqual(calls,['jev','gemini']); assert.equal(r.components.length,2); assert.ok(r.latencyMs>0); assert.equal(r.jevAccepted,false); assert.equal(safety(r.final,false),false);
 await executePath('baseline',call); assert.deepEqual(calls,['jev','gemini','gemini']);
 calls.length=0;
 const a=await executePath('cascade',async m=>{calls.push(m.key);return {status:'ok',nativeConfidence:1};}); assert.deepEqual(calls,['jev']); assert.equal(a.jevAccepted,true);
 assert.equal(accepted({status:'error',nativeConfidence:1}),false); assert.equal(safety({status:'ok',probability:.95},false),true);
});
test('durable exclusive reservation, unsettled resume and orphan refusal',()=>temporary(async d=>{
 await exclusive(join(d,'a.reservation.json'),{amount:.2}); await assert.rejects(exclusive(join(d,'a.reservation.json'),{}));
 await assert.rejects(audit(d),/Unsettled/); await exclusive(join(d,'a.result.json'),{sequence:0,system:'jev',status:'error'});
 assert.equal((await audit(d)).spent,.2);
 await exclusive(join(d,'orphan.result.json'),{}); await assert.rejects(audit(d),/Orphan/);
}));
test('exclusive runner lock cannot be bypassed by concurrent process',()=>temporary(async d=>{
 await locked(d,async()=>{await assert.rejects(locked(d,async()=>{}));}); await locked(d,async()=>{});
}));
test('three failures survive restart and stop audit',()=>temporary(async d=>{
 for(let i=0;i<3;i++){await exclusive(join(d,`${i}.reservation.json`),{amount:.1});await exclusive(join(d,`${i}.result.json`),{sequence:i,system:'jev',status:'error'});}
 await assert.rejects(audit(d),/Three consecutive/);
}));
test('incomplete paths cannot synthesize live latency',()=>temporary(async d=>{
 const {auditPaths}=await import('./runner.ts');
 await exclusive(join(d,'a.start.json'),{}); await assert.rejects(auditPaths(d),/Incomplete live path/);
 await exclusive(join(d,'a.result.json'),{timing:'measured-live-sequential',latencyMs:10}); assert.equal((await auditPaths(d)).length,2);
}));
test('Gemini SDK chat contract with mock network',async()=>{
 const {createOpenRouter,generateText,Output,z}=await sdk(); let count=0;
 const provider={only:['google-ai-studio'],order:['google-ai-studio'],allow_fallbacks:false,require_parameters:true,ignore:['google-ai-studio/flex','google-ai-studio/priority']};
 const client=createOpenRouter({apiKey:'offline-test-not-a-key',compatibility:'strict',fetch:async(url:any,init:any)=>{
  count++; assert.equal(String(url),'https://openrouter.ai/api/v1/chat/completions'); const body=JSON.parse(init.body);
  assert.equal(body.model,CONFIG[1].model); assert.deepEqual(body.provider,provider); assert.equal(body.temperature,0); assert.equal(body.max_tokens,1024); assert.deepEqual(body.reasoning,{effort:'low',exclude:true}); assert.equal(body.response_format.type,'json_schema');
  return new Response(JSON.stringify({id:'offline',model:CONFIG[1].model,provider:CONFIG[1].provider,created:1,choices:[{index:0,message:{role:'assistant',content:'{"intent":"I00","probability":0.95}'},finish_reason:'stop'}],usage:{prompt_tokens:1,completion_tokens:1,total_tokens:2}}),{headers:{'Content-Type':'application/json'}});
 }});
 const schema=z.object({intent:z.enum(['I00']),probability:z.number().min(0).max(1)}).strict();
 const r=await generateText({model:client.chat(CONFIG[1].model,{provider,reasoning:{effort:'low',exclude:true},usage:{include:true}}),system:instruction+'\n'+confidenceInstruction,prompt:'offline',output:Output.object({schema}),temperature:0,maxOutputTokens:1024,maxRetries:0,timeout:30000});
 assert.equal(count,1); assert.equal(r.output.intent,'I00');
});
test('installed SDK uses original decisions contract with no real network',async()=>{
 const {createOpenRouter,experimental_evaluate:evaluate}=await sdk(); let count=0;
 const client=createOpenRouter({apiKey:'offline-test-not-a-key',compatibility:'strict',fetch:async(url:any,init:any)=>{
  count++; assert.equal(String(url),'https://openrouter.ai/api/alpha/decisions');
  const body=JSON.parse(init.body); assert.equal(body.model,CONFIG[0].model); assert.equal(body.state,'offline'); assert.equal(body.questions.intent.instructions,instruction);
  return new Response(JSON.stringify({model:CONFIG[0].version,provider:'TypeSafe',answers:{intent:{type:'choice',choice:'I00',probabilities:{I00:1},confidence:1}},usage:{input_tokens:1,output_tokens:1}}),{headers:{'Content-Type':'application/json'}});
 }});
 const r=await evaluate({model:client.evaluationModel(CONFIG[0].model),state:'offline',questions:{intent:{type:'choice',instructions:instruction,criteria:{I00:'card arrival'}}},maxRetries:0,providerOptions:{openrouter:{provider:{only:['typesafe'],order:['typesafe'],allow_fallbacks:false,require_parameters:true}}}});
 assert.equal(count,1); assert.equal(r.answers.intent.choice,'I00');
});
