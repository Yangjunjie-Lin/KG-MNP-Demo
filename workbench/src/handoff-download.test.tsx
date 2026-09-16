// Component checks only; actual API/Worker download is separately integrated.
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {HandoffDownload,EvolutionDownload} from './handoff-download';

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
