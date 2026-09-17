import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {AgentWorkbench} from './agent-workbench';

const model=vi.hoisted(()=>({permissions:['*'],api:vi.fn()}));
vi.mock('./shell',()=>({useWorkspace:()=>({state:{project:{project_id:'p',authority_revision:1}},principal:{permissions:model.permissions},prefix:'/projects/p'})}));
vi.mock('./api',async()=>({...await vi.importActual('./api'),api:model.api}));
afterEach(()=>{cleanup();model.api.mockReset();model.permissions=['*'];});
function mount(){const navigate=vi.fn();render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><AgentWorkbench stage={2} navigate={navigate} titles={['输入','结构','映射','校验','交付']}/></QueryClientProvider>);return navigate;}
const agents=[{agent_id:'RuleAgent',display_name:'规划 Agent',stages:[1,2,4]},{agent_id:'TaskExecutionAgent',display_name:'任务执行 Agent',stages:[3,5]}];
it('groups the five actual stages into two agents and navigates without executing',async()=>{
  model.api.mockResolvedValue({agents,records:[]});const navigate=mount();
  expect(await screen.findByRole('heading',{name:'规划 Agent'})).toBeVisible();
  expect(screen.getByRole('region',{name:'规划 Agent'}).querySelectorAll('button')).toHaveLength(3);
  expect(screen.getByRole('region',{name:'任务执行 Agent'}).querySelectorAll('button')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button',{name:'S3 · 映射'}));expect(navigate).toHaveBeenCalledWith(3);
});
it('shows failed audits and absent historical content without claiming success',async()=>{
  model.api.mockResolvedValue({agents,records:[{job_id:'j',attempt:1,operation_id:'modeling.proposal',stages:[2,3,4],actor:'TWO_AGENT_OPERATION',job_status:'FAILED',content_mode:'REDACTED_CONTENT',availability:'AVAILABLE'},
    {job_id:'old',attempt:1,stages:[2],job_status:'SUCCEEDED',availability:'ARTIFACT_NOT_AVAILABLE'}]});mount();
  await screen.findByRole('heading',{name:'规划 Agent'});fireEvent.click(screen.getByText('逐步审计文件 · 处理前 / 处理后'));
  expect(screen.getByText('FAILED')).toBeVisible();expect(screen.getByText('未录制（历史内容不可补造）')).toBeVisible();
  expect(screen.getByRole('link',{name:'下载前后审计 ZIP'})).toHaveAttribute('href','/api/v1/projects/p/modeling/audits/j/archive?attempt=1');
});
it('does not expose the download to a source reader without export permissions',async()=>{
  model.permissions=['project:read','job:read','source:read'];model.api.mockResolvedValue({agents,records:[{job_id:'j',stages:[2],availability:'AVAILABLE',job_status:'SUCCEEDED'}]});mount();
  await screen.findByRole('heading',{name:'规划 Agent'});expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
