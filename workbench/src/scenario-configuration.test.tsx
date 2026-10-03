import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {useState} from 'react';
import {MemoryRouter,Outlet,Route,Routes} from 'react-router-dom';
import {ScenarioConfiguration,ScenarioStageResults} from './scenario-configuration';
import {type WorkspaceContext} from './shell';
import {type Document} from './api';

afterEach(cleanup);
function setup(permissions=['*'],legacy=false){
  const onPreview=vi.fn(),onChange=vi.fn(),submit=vi.fn();
  const context={principal:{principal_id:'synthetic',principal_type:'HUMAN',permissions},prefix:'/projects/synthetic',busy:false,submit,
    state:{project:{project_id:'synthetic',domain_pack:'hr',domain_pack_version:'0.1.0'},results:[],jobs:[],modeling_session:legacy?{session_id:'old',scenario:{effective:{scenario_id:'organization_management',scenario_version:'1.0.0'}}}:{},
      scenario_catalogue:[{scenario_id:'organization_management',scenario_version:'2.0.0',name:'企业组织与人员',purpose:'当前与历史',domain_pack:{pack_id:'hr',pack_version:'0.1.0'},
        additions:[1,2,3,4,5].map(s=>[`生成模板 S${s}`,`审核模板 S${s}`])}]}} as unknown as WorkspaceContext;
  function Demo(){const [selection,setSelection]=useState<Document|null>(null);return <ScenarioConfiguration selection={selection} runId="r1" onPreview={onPreview} onChange={v=>{onChange(v);setSelection(v);}}/>;}
  render(<MemoryRouter><Routes><Route element={<Outlet context={context}/>}><Route index element={<Demo/>}/></Route></Routes></MemoryRouter>);
  return {onChange,submit};
}
it('selects only a versioned scene and previews five Prompt pairs without detail controls',()=>{
  const {onChange,submit}=setup();
  fireEvent.click(screen.getByRole('radio'));
  expect(onChange).toHaveBeenLastCalledWith({scenario_id:'organization_management',scenario_version:'2.0.0'});
  fireEvent.click(screen.getByText('五步骤 Prompt 模板预览'));
  for(const stage of [1,2,3,4,5]){
    expect(screen.getByRole('region',{name:`S${stage} 场景 Prompt`})).toHaveTextContent(`生成模板 S${stage}`);
    expect(screen.getByRole('region',{name:`S${stage} 场景 Prompt`})).toHaveTextContent(`审核模板 S${stage}`);
  }
  expect(screen.queryAllByRole('combobox')).toHaveLength(0);
  expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  expect(screen.queryAllByText(/粗细度|粒度|BASIC|STANDARD|DETAILED/)).toHaveLength(0);
  expect(submit).not.toHaveBeenCalled();
});
it('requires existing human scope authority and never displays invented accuracy',()=>{
  setup(['project:read','source:read']);
  expect(screen.getByRole('radio')).toBeDisabled();
  expect(screen.queryByText(/99%|95%|90%/)).not.toBeInTheDocument();
  expect(screen.getByText(/原证据、硬检查和人工审批不变/)).toBeVisible();
});
it('shows an explicit migration notice and does not silently select a new template',()=>{
  setup(['*'],true);
  expect(screen.getByRole('alert')).toHaveTextContent('旧记录保留');
  expect(screen.getByRole('radio')).not.toBeChecked();
});

it('does not present stale artifacts or another package quality as current merely because configuration matches',()=>{
  const context={principal:{principal_id:'synthetic',principal_type:'HUMAN',permissions:['*']},prefix:'/projects/synthetic',busy:false,submit:vi.fn(),
    state:{project:{project_id:'synthetic'},jobs:[],results:[{job_id:'old-job',operation:'compile.build',result:{scenario_outputs:[{stage_id:5,stage_configuration_digest:'same-stage',observed_counts:{STALE_ARTIFACT:999}}]}}],
      modeling_session:{revision:8,scenario:{effective:{scenario_id:'organization_management',scenario_version:'2.0.0',digest:'same-config',stage_digests:{S5:'same-stage'}}},
        scenario_quality:{configuration_digest:'same-config',package_id:'old-package',metrics:{status:'STALE_QUALITY_MARKER',objects:{tp:999}}},
        outputs:[{job_id:'old-job',operation:'compile.build',identifier:'old-package',status:'STALE'},{job_id:'new-job',operation:'compile.build',identifier:'new-package',status:'CURRENT'}],
        expert:{loops:[{job_id:'old-job',current:false,methods:[{stage_id:5,current:false}]}]}}}} as unknown as WorkspaceContext;
  render(<MemoryRouter><Routes><Route element={<Outlet context={context}/>}><Route index element={<ScenarioStageResults stage={5}/>}/></Route></Routes></MemoryRouter>);
  expect(screen.queryAllByText(/STALE_QUALITY_MARKER/)).toHaveLength(0);
  expect(screen.queryAllByText(/STALE_ARTIFACT/)).toHaveLength(0);
  expect(screen.getByText(/当前配置还没有本阶段产物/)).toBeVisible();
});
