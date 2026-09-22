// Offline replay of recorded Jev failures through the installed SDK. No network calls.
import { sdk, CONFIG, instruction } from './runner.ts';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('./', import.meta.url));
const files = (await readdir(root + 'calls')).filter(f => f.endsWith('.result.json'));
const rows = await Promise.all(files.map(async f => JSON.parse(await readFile(root+'calls/'+f,'utf8'))));
const failures = rows.filter(r => r.system === 'jev' && r.status !== 'ok');
const labels: string[] = JSON.parse(await readFile(root+'../categories.json','utf8'));
const criteria = Object.fromEntries(labels.map((s,i) => ['I'+String(i).padStart(2,'0'),s.replaceAll('_',' ')]));
const { createOpenRouter, experimental_evaluate: evaluate } = await sdk();
const results = [];
for (const row of failures) {
  let mockedCalls = 0;
  const client = createOpenRouter({ apiKey: 'offline-fixture-not-a-credential', fetch: async () => {
    mockedCalls++;
    return new Response(JSON.stringify(row.response), { headers: { 'Content-Type': 'application/json' } });
  }});
  try {
    await evaluate({ model: client.evaluationModel(CONFIG[0].model), state: 'offline replay of saved response',
      questions: {intent: {type:'choice',instructions:instruction,criteria}}, maxRetries:0 });
    results.push({caseId:row.caseId,reproduced:false,mockedCalls});
  } catch (e) {
    results.push({caseId:row.caseId,reproduced:true,mockedCalls,errorName:e instanceof Error?e.name:'Error',errorMessage:e instanceof Error?e.message:'Unknown'});
  }
}
const result = {networkCalls:0,source:'Saved provider response injected as SDK mock transport; original records unchanged',results};
await writeFile(root+'failure-replay.json',JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
