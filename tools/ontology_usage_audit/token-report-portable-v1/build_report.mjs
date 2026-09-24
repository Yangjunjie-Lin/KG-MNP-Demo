import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const wb = Workbook.create();
if (process.argv.includes('--discover-csv')) {
  console.log(wb.help('SpreadsheetFile.exportCsv', { include: 'index,examples,notes', maxChars: 2000 }).ndjson);
} else {
  await build();
}

function letter(n) {
  let result = '';
  for (n++; n; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + (n - 1) % 26) + result;
  return result;
}

async function build() {
  const input = process.argv[2] || path.join(here, 'snapshot-delivery.json');
  const output = process.argv[3] || path.resolve(here, '../../../outputs/01a0c3f7-597f-7be2-97df-cd64d43ff5ab/llm-token-20260923');
  const data = JSON.parse(await fs.readFile(input, 'utf8'));
  await fs.mkdir(output, { recursive: true });
  const previewDir = path.join(here, 'previews');
  await fs.mkdir(previewDir, { recursive: true });
  const font = 'Arial';
  const ink = '#172B4D', muted = '#526278', rule = '#D8DFE8', head = '#263F60';
  const summary = wb.worksheets.add('汇总');
  const calls = wb.worksheets.add('调用明细');
  const flows = wb.worksheets.add('流程总量');
  const stages = wb.worksheets.add('阶段汇总');
  const notes = wb.worksheets.add('统计口径');
  const fields = ['revision','phase','system','stage','purpose','input_tokens','output_tokens','total_tokens','usage_status','state',
    'job_id','attempt','call_index','is_repair','request_id','started_at_utc','ended_at_utc','budget_charge','role','task','sample_id','replicate',
    'response_verification','request_file_sha256','response_semantic_sha256','stage_basis','call_qualification'];
  const headers = ['生成版本','批次','方法','建模阶段','调用步骤','输入 tokens','输出 tokens','报告总 tokens','用量状态','调用状态',
    '作业 ID','执行尝试','尝试内调用序号','修复调用 1/0','调用 ID','开始 UTC','结束 UTC','预算占用 tokens','计算角色','任务类型','样本 ID','重复轮次',
    '响应核验','请求文件 SHA256','响应内容 SHA256','阶段对应依据','调用计数口径'];
  const unknownCol = letter(fields.length), missingCol = letter(fields.length + 1);
  const col = key => letter(fields.indexOf(key));
  const rank = r => r === data.active_revision ? 0 : r === 'HISTORICAL_PROBE' ? 2 : 1;
  const sorted = [...data.calls].sort((a,b) => [rank(a.revision),a.revision,a.phase,a.job_id,a.attempt ?? 0,a.call_index ?? 0].join('|')
    .localeCompare([rank(b.revision),b.revision,b.phase,b.job_id,b.attempt ?? 0,b.call_index ?? 0].join('|')));
  const processes = [...data.processes].sort((a,b) => rank(a.revision)-rank(b.revision) || a.revision.localeCompare(b.revision)
    || a.phase.localeCompare(b.phase) || (b.started ?? '').localeCompare(a.started ?? '') || a.job_id.localeCompare(b.job_id));
  const last = sorted.length + 4;
  const range = key => `'调用明细'!$${col(key)}$5:$${col(key)}$${last}`;
  const special = c => `'调用明细'!$${c}$5:$${c}$${last}`;
  const nums = r => r.format.numberFormat = '#,##0';
  function base(sheet, title, width, rows) {
    const used = sheet.getRange(`A1:${letter(width - 1)}${rows}`);
    used.format.font = { name: font, size: 10, color: ink };
    used.format.rowHeight = 22;
    used.format.columnWidth = 16;
    used.format.verticalAlignment = 'center';
    sheet.showGridLines = false;
    sheet.getRange('A1').values = [[title]];
    sheet.getRange('A1').format.font = { name: font, size: 17, bold: true, color: ink };
    sheet.getRange('A1').format.rowHeight = 31;
    sheet.getRange(`A1:${letter(width - 1)}1`).format.borders = { bottom: {style:'thin', color:rule} };
    sheet.getRange('A2').values = [['快照时间 UTC']];
    sheet.getRange('B2').values = [[new Date(data.snapshot_started_at_utc)]];
    sheet.getRange('B2').setNumberFormat('yyyy-mm-dd hh:mm:ss');
    sheet.getRange('A2:B2').format.font = { name: font, size: 10, color: muted };
    sheet.getRange('B:B').format.columnWidth = 23;
  }
  function header(sheet, address) {
    const r = sheet.getRange(address);
    r.format.fill = head;
    r.format.font = { name:font, size:10, bold:true, color:'#FFFFFF' };
    r.format.wrapText = true;
    r.format.rowHeight = 34;
    r.format.horizontalAlignment = 'center';
    r.format.verticalAlignment = 'center';
    r.format.borders = { insideVertical: {style:'thin', color:'#FFFFFF'} };
  }
  function table(sheet, headings, values, name) {
    sheet.getRangeByIndexes(3,0,1,headings.length).values = [headings];
    if (values.length) sheet.getRangeByIndexes(4,0,values.length,headings.length).values = values;
    const t = sheet.tables.add(`A4:${letter(headings.length - 1)}${Math.max(4, values.length + 4)}`, true, name);
    t.showFilterButton = true;
    header(sheet, `A4:${letter(headings.length - 1)}4`);
    sheet.freezePanes.freezeRows(4);
  }

  base(calls, '逐次 LLM 调用', fields.length + 2, last);
  const callValues = sorted.map(r => [...fields.map(k => k.endsWith('_at_utc') ? (r[k] ? new Date(r[k]) : null)
    : k === 'is_repair' ? Number(r[k]) : r[k] ?? null), null, null]);
  table(calls, [...headers, '总量未知 1/0', '分项缺失 1/0'], callValues, 'LlmCalls');
  calls.getRange(`${unknownCol}5`).formulas = [[`=IF(ISNUMBER(${col('total_tokens')}5),0,1)`]];
  calls.getRange(`${unknownCol}5:${unknownCol}${last}`).fillDown();
  calls.getRange(`${missingCol}5`).formulas = [[`=IF(COUNT(${col('input_tokens')}5:${col('output_tokens')}5)=2,0,1)`]];
  calls.getRange(`${missingCol}5:${missingCol}${last}`).fillDown();
  calls.getRange('A:A').format.columnWidth = 28;
  calls.getRange('C:C').format.columnWidth = 30;
  calls.getRange('D:D').format.columnWidth = 27;
  calls.getRange('E:E').format.columnWidth = 21;
  calls.getRange('I:J').format.columnWidth = 23;
  calls.getRange('J:J').format.columnWidth = 32;
  calls.getRange('K:K').format.columnWidth = 32;
  calls.getRange('O:O').format.columnWidth = 55;
  calls.getRange('P:Q').format.columnWidth = 24;
  calls.getRange('S:V').format.columnWidth = 29;
  calls.getRange('W:AC').format.columnWidth = 70;
  calls.getRange(`${unknownCol}:${missingCol}`).format.columnWidth = 17;
  calls.getRange('X:Y').setNumberFormat('@');
  nums(calls.getRange(`F5:H${last}`)); nums(calls.getRange(`R5:R${last}`));
  calls.getRange(`P5:Q${last}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');
  calls.getRange(`F5:H${last}`).format.horizontalAlignment = 'right';
  calls.getRange(`I5:I${last}`).conditionalFormats.add('containsText', {text:'UNKNOWN', format:{fill:'#FFF0CA'}});
  calls.getRange(`I5:I${last}`).conditionalFormats.add('containsText', {text:'IN_FLIGHT', format:{fill:'#FFF0CA'}});

  // Grouped call blocks keep per-workflow formulas short and inexpensive.
  const blocks = new Map();
  sorted.forEach((r,i) => { const x = blocks.get(r.job_id); if (x) x.end=i+5; else blocks.set(r.job_id,{start:i+5,end:i+5}); });
  const flowHeaders = ['生成版本','批次','方法','流程状态','调用尝试','已知输入 tokens','已知输出 tokens','已知总 tokens','未知用量调用',
    '完整流程总 tokens','总量说明','S2 已知 tokens','S3 已知 tokens','直接对照已知 tokens','未归类已知 tokens','有调用的尝试数','作业 ID','样本 ID','重复轮次','开始 UTC','结束 UTC','快照前已结束'];
  const flowRows = processes.map(r => [r.revision,r.phase,r.system,r.state,null,null,null,null,null,null,null,null,null,null,null,
    r.execution_attempts_with_calls,r.job_id,r.sample,r.replicate,r.started ? new Date(r.started) : null,r.ended ? new Date(r.ended) : null,
    !!(r.ended && Date.parse(r.ended)<=Date.parse(data.snapshot_started_at_utc) && ['GENERATED','FAILED'].includes(r.state))]);
  base(flows, '每个流程的累计用量', flowHeaders.length, flowRows.length+4);
  table(flows, flowHeaders, flowRows, 'WorkflowUsage');
  for (let i=0; i<processes.length; i++) {
    const r=processes[i], n=i+5, b=blocks.get(r.job_id);
    const br = key => `'调用明细'!$${col(key)}$${b.start}:$${col(key)}$${b.end}`;
    const values = b ? [`=ROWS(${br('request_id')})`,`=SUM(${br('input_tokens')})`,`=SUM(${br('output_tokens')})`,`=SUM(${br('total_tokens')})`,
      `=SUM('调用明细'!$${unknownCol}$${b.start}:$${unknownCol}$${b.end})`] : ['=0','=0','=0','=0','=0'];
    flows.getRange(`E${n}:I${n}`).formulas = [values];
    flows.getRange(`J${n}:K${n}`).formulas = [[`=IF(AND(V${n}=TRUE,I${n}=0),H${n},"")`,
      `=IF(V${n}=TRUE,IF(I${n}=0,"完整报告用量","历史用量未知"),"仍在执行或未确认结束")`]];
    flows.getRange(`L${n}:N${n}`).formulas = [[...['S2','S3','DIRECT'].map(s => b ? `=SUMIF(${br('stage')},"${s}",${br('total_tokens')})` : '=0')]];
    flows.getRange(`O${n}`).formulas = [[`=H${n}-SUM(L${n}:N${n})`]];
  }
  flows.getRange('A:A').format.columnWidth = 20;
  flows.getRange('C:C').format.columnWidth = 30;
  flows.getRange('D:D').format.columnWidth = 18;
  flows.getRange('E:P').format.columnWidth = 18;
  flows.getRange('K:K').format.columnWidth = 30;
  flows.getRange('Q:R').format.columnWidth = 38;
  flows.getRange('T:U').format.columnWidth = 24;
  nums(flows.getRange(`E5:J${flowRows.length+4}`)); nums(flows.getRange(`L5:P${flowRows.length+4}`));
  flows.getRange(`T5:U${flowRows.length+4}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');

  const stageHeaders = ['批次','方法','建模阶段','调用步骤','计算角色','修复调用 1/0','调用尝试','已知输入 tokens','已知输出 tokens','已知总 tokens','未知用量调用'];
  base(stages, '当前 r8 阶段用量', stageHeaders.length, data.stages.length+4);
  table(stages, stageHeaders, data.stages.map(r => [r.phase,r.system,r.stage,r.purpose,r.role,Number(r.is_repair),null,null,null,null,null]), 'StageUsage');
  for (let i=0;i<data.stages.length;i++) {
    const n=i+5;
    const criteria=[range('phase'),`A${n}`,range('system'),`B${n}`,range('stage'),`C${n}`,range('purpose'),`D${n}`,range('is_repair'),`F${n}`,range('revision'),`"${data.active_revision}"`].join(',');
    stages.getRange(`G${n}:K${n}`).formulas = [[`=COUNTIFS(${criteria})`,...['input_tokens','output_tokens','total_tokens'].map(k=>`=SUMIFS(${range(k)},${criteria})`),`=SUMIFS(${special(unknownCol)},${criteria})`]];
  }
  stages.getRange('A:A').format.columnWidth = 18;
  stages.getRange('B:B').format.columnWidth = 30;
  stages.getRange('D:E').format.columnWidth = 27;
  stages.getRange('G:K').format.columnWidth = 19;
  nums(stages.getRange(`G5:K${data.stages.length+4}`));

  base(summary, 'LLM Token 用量', 8, 26);
  summary.getRange('A:A').format.columnWidth = 39;
  summary.getRange('B:H').format.columnWidth = 22;
  summary.getRange('A3').values = [['全量测试继续运行，本表为累计快照']];
  summary.getRange('A3').format.font = {name:font,size:10,color:muted};
  summary.getRange('A4:H4').values = [['统计范围','调用尝试','已知输入 tokens','已知输出 tokens','已知总 tokens','总量未知调用','分项缺失调用','用量完整性']];
  header(summary,'A4:H4');
  data.scopes.forEach((r,i) => {
    const n=i+5;
    summary.getRange(`A${n}`).values = [[r.scope]];
    const criteria = i===0 ? '' : [range('revision'),`"${data.active_revision}"`,...(i===2 ? [range('phase'),'"full"'] : [])].join(',');
    const sum = ref => criteria ? `=SUMIFS(${ref},${criteria})` : `=SUM(${ref})`;
    summary.getRange(`B${n}:G${n}`).formulas = [[criteria ? `=COUNTIFS(${criteria})` : `=ROWS(${range('request_id')})`,
      ...['input_tokens','output_tokens','total_tokens'].map(k=>sum(range(k))),sum(special(unknownCol)),sum(special(missingCol))]];
    summary.getRange(`H${n}`).formulas = [[`=IF(F${n}>0,"含未知用量","快照内总量已知")`]];
  });
  summary.getRange('A5:H7').format.rowHeight = 35;
  summary.getRange('A5:A7').format.wrapText = true;
  nums(summary.getRange('B5:G7'));
  summary.getRange('A10').values = [['当前 r8 按建模阶段']];
  summary.getRange('A10').format.font = {name:font,size:12,bold:true,color:ink};
  summary.getRange('A11:H11').values = [['建模阶段','调用尝试','已知输入 tokens','已知输出 tokens','已知总 tokens','总量未知调用','阶段性质','计算角色']];
  header(summary,'A11:H11');
  const stageDefs=[['S1','S1 输入核验','程序步骤','RuleAgent'],['S2','S2 结构设计','含 LLM 调用','RuleAgent'],
    ['S3','S3 事实构建','含 LLM 调用','TaskExecutionAgent'],['S4','S4 联合校验','程序步骤','RuleAgent'],
    ['S5','S5 编译交付','程序步骤','TaskExecutionAgent'],['DIRECT','直接对照调用','非五阶段','直接对照'],['UNKNOWN','未能归类','不猜测步骤','']];
  stageDefs.forEach(([stage,label,nature,role],i)=>{
    const n=i+12, criteria=[range('revision'),`"${data.active_revision}"`,range('stage'),`"${stage}"`].join(',');
    summary.getRange(`A${n}`).values=[[label]];
    summary.getRange(`B${n}:F${n}`).formulas=[[`=COUNTIFS(${criteria})`,...['input_tokens','output_tokens','total_tokens'].map(k=>`=SUMIFS(${range(k)},${criteria})`),`=SUMIFS(${special(unknownCol)},${criteria})`]];
    summary.getRange(`G${n}:H${n}`).values=[[nature,role]];
  });
  nums(summary.getRange('B12:F18'));
  summary.getRange('G12:H18').format.wrapText=true;
  summary.getRange('A12:H18').format.rowHeight=32;
  summary.getRange('A21').values=[['预算占用（不是实际用量）']];
  summary.getRange('E21').formulas=[[`=SUM(${range('budget_charge')})`]];
  nums(summary.getRange('E21'));
  summary.getRange('A23').values=[['全量最终总量尚未形成']];
  summary.getRange('A24').values=[['统计口径与缺失说明见“统计口径”页']];
  summary.getRange('A23:A24').format.font={name:font,size:10,color:muted};

  const noteRows = [
    ['统计范围','同一研究实验账本。包括历史诊断、smoke、pilot、full、失败及重试；不含本次Codex聊天或其他项目的模型用量。'],
    ['当前版本',data.active_revision],
    ['快照 UTC',data.snapshot_started_at_utc],
    ['输入/输出来源','从原公开回执读取 prompt_tokens / completion_tokens；Responses诊断的 input_tokens / output_tokens 按原字段对应。均先验证响应内容SHA。'],
    ['总量来源','每个 request_id 只计一次，以原 attempts.usage 为报告总量；已知小计只求和已返回的数值。'],
    ['未知用量','空白表示未知，不是0。失败及在途请求缺失usage时不补造，完整流程总量保持空白。'],
    ['预算占用','预算占用包含保守预留，不是实际token使用量；不会拿预留值替代usage，也不在报告中退款。'],
    ['阶段对应','按实际记录的请求结构与相应冻结源码匹配，不按调用序号猜阶段。直接对照方法单列，不冒称五阶段。'],
    ['修复归属','S4是程序校验；它触发的LLM修复实际发生在S2或S3，计入相应步骤。修复调用1=是，0=否。'],
    ['程序步骤','当前冻结内核的S1、S4、S5没有直接LLM调用；表中的0仅表示LLM用量，不代表程序或语义验收通过。'],
    ['单流程总量','流程总量页按原job_id合计所有调用尝试；仅在流程已结束且所有总量已知时给出完整总量。失败流程照样保留。'],
    ['调用次数','次数是账本中的caller调用尝试，包含失败、重试及本地拒绝；不是独立核证的物理HTTP发送次数。'],
    ['状态字段','COMPLETE=输入输出总量一致；TOTAL_ONLY=只有总量；UNKNOWN=未返回用量；IN_FLIGHT=快照时在途。'],
    ['响应核验',`${Object.values(data.source_coverage).reduce((a,b)=>a+b,0)}条账本记录逐条纳入；异常对账项${data.issues.length}项。`],
    ['快照摘要',data.source_snapshot_sha256],
    ['明细摘要',data.call_table_sha256],
    ['来源','原研究budget.sqlite的attempts/monitored_attempts、jobs.sqlite及对应请求/公开响应记录。报告无Prompt、源文本、答案或密钥。'],
    ['自动更新','本文件是固定快照。全量继续运行，最终结束后需按同一口径重新生成最终累计报告。'],
  ];
  base(notes,'统计口径',2,noteRows.length+4);
  table(notes,['项目','说明'],noteRows,'UsageDefinitions');
  notes.freezePanes.unfreeze();
  notes.getRange('A:A').format.columnWidth=27;
  notes.getRange('B:B').format.columnWidth=112;
  notes.getRange(`A5:B${noteRows.length+4}`).format.wrapText=true;
  notes.getRange(`A5:B${noteRows.length+4}`).format.rowHeight=42;
  notes.getRange('B7').values=[[new Date(data.snapshot_started_at_utc)]];
  notes.getRange('B7').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  notes.getRange('B2').format.rowHeight=22;

  // Independent integer reconciliation against the source extractor's SQL sums.
  const summaryValues=summary.getRange('B5:G7').values;
  data.scopes.forEach((s,i)=>{
    const expected=[s.calls,s.known_input,s.known_output,s.known_total,s.unknown_total_calls,s.missing_breakdown_calls];
    if (JSON.stringify(summaryValues[i])!==JSON.stringify(expected)) throw new Error(`SUMMARY_RECONCILIATION_${i}: ${JSON.stringify(summaryValues[i])} != ${JSON.stringify(expected)}`);
  });
  processes.forEach((r,i)=>{
    const observed=flows.getRange(`E${i+5}:I${i+5}`).values[0];
    const expected=[r.calls,r.known_input,r.known_output,r.known_total,r.unknown_total_calls];
    if (JSON.stringify(observed)!==JSON.stringify(expected)) throw new Error(`FLOW_RECONCILIATION_${r.job_id}`);
  });
  data.stages.forEach((r,i)=>{
    if (JSON.stringify(stages.getRange(`G${i+5}:K${i+5}`).values[0])!==JSON.stringify([r.calls,r.known_input,r.known_output,r.known_total,r.unknown_total_calls]))
      throw new Error(`STAGE_RECONCILIATION_${i}`);
  });
  const inspected=await wb.inspect({kind:'table',range:'汇总!A4:H18',include:'values,formulas',tableMaxRows:18,tableMaxCols:8,maxChars:3500});
  console.log(inspected.ndjson);
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'Formula errors'});
  console.log(errors.ndjson);
  await fs.writeFile(path.join(here,'workbook-inspection.ndjson'),inspected.ndjson+'\n'+errors.ndjson);
  for (const [sheetName,rangeToRender,name] of [['汇总','A1:H24','summary'],['调用明细','A1:J15','calls'],['流程总量','A1:K15','flows'],['阶段汇总','A1:K17','stages'],['统计口径','A1:B14','notes']]) {
    const blob=await wb.render({sheetName,range:rangeToRender,scale:1,format:'png'});
    await fs.writeFile(path.join(previewDir,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
  }
  const csvValue=v=>`"${String(v ?? '').replaceAll('"','""')}"`;
  // Public API has no CSV exporter (one bounded help lookup returned no entry).
  // Serialize the same authored flat observations, preserving null as blank.
  const csvRows=[headers,...sorted.map(r=>fields.map(k=>k==='is_repair'?Number(r[k]):r[k]??''))];
  await fs.writeFile(path.join(output,'llm-token-calls.csv'),'\uFEFF'+csvRows.map(r=>r.map(csvValue).join(',')).join('\r\n')+'\r\n','utf8');
  const outputFile=await SpreadsheetFile.exportXlsx(wb);
  await outputFile.save(path.join(output,'LLM-Token-Usage.xlsx'));
  const fmt=n=>n==null?'未知':n.toLocaleString('en-US');
  const stageNumbers=summary.getRange('B12:F18').values;
  const md=['# LLM Token 使用报告','',`快照时间：${data.snapshot_started_at_utc}。全量测试继续运行。`,'',
    '## 累计用量','', '| 范围 | 调用尝试 | 已知输入 tokens | 已知输出 tokens | 已知总 tokens | 总量未知调用 |',
    '|---|---:|---:|---:|---:|---:|',...data.scopes.map(s=>`| ${s.scope} | ${fmt(s.calls)} | ${fmt(s.known_input)} | ${fmt(s.known_output)} | ${fmt(s.known_total)} | ${fmt(s.unknown_total_calls)} |`),'',
    '## 当前 r8 的步骤用量','', '| 步骤 | 调用尝试 | 已知输入 tokens | 已知输出 tokens | 已知总 tokens | 总量未知调用 |', '|---|---:|---:|---:|---:|---:|',
    ...stageDefs.map((r,i)=>`| ${r[1]} | ${stageNumbers[i].map(fmt).join(' | ')} |`),'',
    '## 说明','',...data.limitations.map(s=>'- '+s),
    '- 单个流程的完整用量、所有尝试及逐调用明细见工作簿；每个流程按原 job_id 汇总，包含失败和重试。',
    '- 不含本次聊天、报告编制或其他项目的Codex用量。','',
    `逐条对账：${fmt(sorted.length)} 个调用ID，已知总量与原账本一致；对账异常 ${data.issues.length} 项。`,'',
    '[工作簿](LLM-Token-Usage.xlsx)　[逐调用 CSV](llm-token-calls.csv)',''];
  await fs.writeFile(path.join(output,'TOKEN_REPORT.md'),md.join('\n'),'utf8');
  await fs.writeFile(path.join(here,'authoring-receipt.json'),JSON.stringify({snapshot:data.snapshot_started_at_utc,output,call_rows:sorted.length,
    process_rows:data.processes.length,stage_rows:data.stages.length,integer_reconciliation:true,font:{family:font,windows_file:'arial.ttf'},
    model_calls_by_report:0,formula_inspection:errors.ndjson},null,2)+'\n');
  console.log(JSON.stringify({output,calls:sorted.length,processes:data.processes.length,stages:data.stages.length,reconciled:true}));
}
