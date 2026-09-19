// Component checks only; actual API/Worker download is separately integrated.
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {HandoffDownload,EvolutionDownload,TrajectoryReview,EvolutionBatchDownload,DeliveryChecklist} from './handoff-download';

const model=vi.hoisted(()=>({workspace:{state:{project:{project_id:'synthetic',authority_revision:1},jobs:[{job_id:'export',status:'SUCCEEDED',error:null as {code:string}|null}],results:[] as unknown[]},
  principal:{permissions:['*']},prefix:'/projects/synthetic',busy:false},post:vi.fn(),api:vi.fn()}));
vi.mock('./shell',()=>({useWorkspace:()=>model.workspace}));
vi.mock('./api',async()=>{const original=await vi.importActual('./api');return {...original,post:model.post,api:model.api};});
afterEach(()=>{cleanup();model.post.mockReset();model.api.mockReset();model.workspace.state.results=[];model.workspace.principal.permissions=['*'];model.workspace.state.jobs=[{job_id:'export',status:'SUCCEEDED',error:null}];});
function mount(view:React.ReactNode){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>{view}</QueryClientProvider>);}

it('requires explicit license and recipient before submitting a real service operation',async()=>{
  model.api.mockResolvedValue({status:'READY',expected_revision:4,sources:[{source_id:'s',sha256:'hash',name:'synthetic.csv'}]});
  model.post.mockResolvedValue({status:'ACCEPTED'});
  mount(<HandoffDownload packageId="native-package"/>);
  fireEvent.click(screen.getByRole('button',{name:'本体交接包'}));
  expect(screen.getByRole('button',{name:'确认授权并生成交接包'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('接收人'),{target:{value:'authorized recipient'}});
  fireEvent.change(screen.getByLabelText('来源许可'),{target:{value:'synthetic license'}});
  fireEvent.change(screen.getByLabelText('导出授权依据'),{target:{value:'explicit synthetic test'}});
  await waitFor(()=>expect(screen.getByRole('button',{name:'确认授权并生成交接包'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'确认授权并生成交接包'}));
  await waitFor(()=>expect(model.post).toHaveBeenCalledWith('/operations/modeling.handoff.export',expect.objectContaining({expected_revision:4,package_id:'native-package'})));
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it('downloads only server-produced artifacts and distinguishes local diagnostic from v2',()=>{
  model.workspace.state.results=[{operation:'modeling.evolution.export',job_id:'export',result:{source_job_id:'failed-job',status:'LOCAL_DIAGNOSTIC_EXPORTED'}}];
  mount(<EvolutionDownload jobId="failed-job"/>);
  expect(screen.getByRole('link',{name:'下载本地诊断（非 v2）'})).toHaveAttribute('href','/api/v1/projects/synthetic/handoffs/export/archive');
});

it('does not offer content trace export without its separate permission',()=>{
  model.workspace.principal.permissions=['package:export','source:read'];
  mount(<EvolutionDownload jobId="private-job"/>);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it('shows the actual failed asynchronous export instead of implying success',async()=>{
  model.workspace.state.jobs=[{job_id:'export',status:'FAILED',error:{code:'EVOLUTION_STRICT_V2_BLOCKED'}}];
  model.post.mockResolvedValue({job_id:'export'});
  mount(<EvolutionDownload jobId="program-job"/>);
  fireEvent.click(screen.getByRole('button',{name:'演进数据包'}));
  await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('FAILED EVOLUTION_STRICT_V2_BLOCKED'));
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it('submits pass without annotations and preserves optional JSON without a client reviewer',async()=>{
  model.post.mockResolvedValue({job_id:'review-job'});
  mount(<TrajectoryReview jobId="source-job"/>);
  fireEvent.change(screen.getByLabelText('violations（可选 JSON 数组）'),{target:{value:'[{"code":"domain-code","evidence":{"iri":"urn:test"},"suggestion":"check"}]'}});
  fireEvent.change(screen.getByLabelText('corrected_answer（可选 JSON）'),{target:{value:'["opaque",{"role":"business-value"}]'}});
  fireEvent.click(screen.getByRole('button',{name:'以当前身份提交运行评价'}));
  await waitFor(()=>expect(model.post).toHaveBeenCalledWith('/operations/modeling.evolution.review',{
    project_id:'synthetic',job_id:'source-job',verdict:'pass',violations:[{code:'domain-code',evidence:{iri:'urn:test'},suggestion:'check'}],corrected_answer:['opaque',{role:'business-value'}]}));
});

it('requires fail annotations and reports invalid JSON without submitting',async()=>{
  mount(<TrajectoryReview jobId="source-job"/>);
  fireEvent.change(screen.getByLabelText('运行评价结论'),{target:{value:'fail'}});
  expect(screen.getByRole('button',{name:'以当前身份提交运行评价'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('annotations（fail 必填，JSON 数组）'),{target:{value:'not json'}});
  fireEvent.click(screen.getByRole('button',{name:'以当前身份提交运行评价'}));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(model.post).not.toHaveBeenCalled();
});

it('uses the same review form for a trusted historical run',async()=>{
  model.post.mockResolvedValue({job_id:'historical-review'});
  mount(<TrajectoryReview jobId="current-job"/>);
  fireEvent.change(screen.getByLabelText('评价对象'),{target:{value:'historical'}});
  fireEvent.change(screen.getByLabelText('历史运行 exec_id'),{target:{value:'previous-run'}});
  fireEvent.change(screen.getByLabelText('可信执行导出任务 ID'),{target:{value:'previous-export'}});
  fireEvent.click(screen.getByRole('button',{name:'以当前身份提交运行评价'}));
  await waitFor(()=>expect(model.post).toHaveBeenCalledWith('/operations/modeling.evolution.review',{
    project_id:'synthetic',exec_id:'previous-run',execution_export_job_id:'previous-export',verdict:'pass'}));
});

it('exports an explicit empty batch through the Worker and does not show a premature download',async()=>{
  model.post.mockResolvedValue({job_id:'empty-job'});
  mount(<EvolutionBatchDownload/>);
  fireEvent.change(screen.getByLabelText('演进批次编号'),{target:{value:'empty'}});
  fireEvent.click(screen.getByRole('button',{name:'生成所选演进批次'}));
  await waitFor(()=>expect(model.post).toHaveBeenCalledWith('/operations/modeling.evolution.export',{
    project_id:'synthetic',batch_id:'empty',review_ids:[],known_run_export_job_ids:[]}));
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

it('keeps the 17-item checklist in three expandable groups',()=>{
  mount(<DeliveryChecklist/>);
  for(const label of ['01–08 上游输入','09–14 本体成果','15–17 演进数据'])expect(screen.getByText(label).tagName).toBe('SUMMARY');
  expect(screen.getByText(/精简版（名称更新版，经用户确认）/)).toBeInTheDocument();
  expect(screen.getByText(/01 表格数据 records.json/)).toHaveTextContent('02 文本片段 text_blocks.json');
  expect(screen.queryByText(/^18 /)).not.toBeInTheDocument();
});
