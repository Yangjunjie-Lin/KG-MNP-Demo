// Component projections use synthetic API responses; never counted as E2E.
import {afterEach,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter} from 'react-router-dom';
import {api,post,type ProjectState} from './api';
import {ObjectBrowser} from './object-browser';
import {FieldMappingPreview} from './field-mapping-preview';
import {ProjectOverview,projectArtifacts} from './project-overview';
import {ReleaseReview} from './release-review';

const context=vi.hoisted(()=>({state:{project:{project_id:'project-1',domain_pack:'synthetic',domain_pack_version:'0.1.0',status:'OPEN',authority_revision:4},results:[],jobs:[]} as unknown as ProjectState,prefix:'/projects/project-1',principal:{principal_id:'human',principal_type:'HUMAN'},busy:false,submit:vi.fn()}));
vi.mock('./shell',()=>({useWorkspace:()=>context}));
vi.mock('./api',async importOriginal=>({...await importOriginal<typeof import('./api')>(),api:vi.fn(),post:vi.fn()}));
const clients:QueryClient[]=[];
function mount(element:React.ReactNode){const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>);}
function entry(operation:string,result:Record<string,unknown>,revision=1){return {job_id:'job-'+revision,operation,result,revision};}
const page=(package_id:string,rows:Record<string,unknown>[])=>({package_id,release_id:null,rows,page:{offset:0,limit:100,truncated:false}});
function metadata(){vi.mocked(api).mockResolvedValue({package_id:'p1',view:'VALIDATED_UNPUBLISHED',semantic_digest:'digest',rows:[],page:{offset:0,limit:100,total:201}});}
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.resetAllMocks();context.state.results=[];context.state.jobs=[];});

it('projects actual artifact IDs and reads pending review rather than inventing completion',async()=>{
  context.state.results=[entry('source.register',{batch:{batch_id:'batch-1'}}),entry('modeling.proposal',{proposal:{proposal_id:'proposal-1'},queue:{review_queue_id:'review-1'}},2),entry('compile.build',{package_id:'package-1'},3),entry('release.publish',{release:{release_id:'release-1'}},4)];
  context.state.jobs=[{job_id:'blocked-job',operation_id:'compile.build',status:'RECOVERY_REQUIRED',attempt:1,error:{code:'AUTH_REVOKED'}}];
  vi.mocked(api).mockResolvedValue({status:{remaining_count:2,inconsistent_candidate_ids:[],requested_evidence_candidate_ids:['candidate-1']}});
  expect(projectArtifacts(context.state)).toMatchObject({batch:'batch-1',proposal:'proposal-1',compilation:'package-1',release:'release-1'});
  mount(<ProjectOverview/>);
  expect(await screen.findByText(/待形成一致决定：2/)).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'release-1'})).toHaveAttribute('href','/projects/project-1/releases');
  expect(screen.getByRole('columnheader',{name:'阻断原因'})).toBeInTheDocument();
  expect(screen.getByText('AUTH_REVOKED')).toBeInTheDocument();
});

it('keeps an empty project explicitly empty without querying an invented review',()=>{
  mount(<ProjectOverview/>);
  expect(screen.getByText('尚无审核队列。')).toBeInTheDocument();
  expect(screen.getAllByText('尚未生成')).toHaveLength(6);
  expect(api).not.toHaveBeenCalled();
});

it('binds release controls to candidate identity and disables already-published candidates',()=>{
  context.state.results=[entry('release.publish',{release:{release_candidate_id:'old-candidate',release_id:'old-release'}})];
  mount(<ReleaseReview candidates={[{release_candidate_id:'old-candidate'},{release_candidate_id:'new-candidate'}]} reviews={[{release_candidate_id:'old-candidate',quorum_satisfied:true,finalized:true,review_id:'review-old',actions:[]}]}/>);
  const old=screen.getByTestId('release-candidate-old-candidate');
  expect(old.querySelectorAll('button:disabled').length).toBeGreaterThanOrEqual(2);
  expect(screen.getByTestId('release-candidate-new-candidate').querySelector('button')).not.toBeDisabled();
  expect(screen.getByText('此候选已经发布；后续变化必须使用新的 Release Candidate。')).toBeInTheDocument();
});

it('binds mapping samples to their exact dataset run and renders source/type/target',async()=>{
  context.state.results=[entry('ingestion.run',{dataset_id:'wrong',run:{run_id:'wrong-run'}}),entry('ingestion.run',{dataset_id:'wanted',run:{run_id:'verified-run'}},2)];
  vi.mocked(api).mockResolvedValue({evidence:[{observed_value:'Synthetic source sample',source_id:'source-1',evidence_id:'evidence-1',locator:{row:2}}]});
  mount(<FieldMappingPreview prepared={{mappings:{kg_ir_dataset_ids:['wanted'],mappings:[{field_mapping_id:'map-1',source_item_id:'item-1',source_field_name:'label',source_datatype:'STRING',target_property_iri:'urn:label',null_policy:'OMIT'}]}}}/>);
  fireEvent.change(screen.getByLabelText('选择映射查看原始样本'),{target:{value:'map-1'}});
  expect(await screen.findByText('Synthetic source sample')).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith('/projects/project-1/evidence?run_id=verified-run&item_id=item-1',expect.any(Object));
  expect(screen.getByRole('link',{name:/下载映射样本来源/})).toHaveAttribute('href','/api/v1/projects/project-1/sources/source-1/content');
});

it('does not replace absent sample authority with a different successful ingestion',()=>{
  context.state.results=[entry('ingestion.run',{dataset_id:'wrong',run:{run_id:'wrong-run'}})];
  mount(<FieldMappingPreview prepared={{mappings:{kg_ir_dataset_ids:['wanted'],mappings:[{field_mapping_id:'map-1',source_item_id:'item-1'}]}}}/>);
  fireEvent.change(screen.getByLabelText('选择映射查看原始样本'),{target:{value:'map-1'}});
  expect(screen.getByRole('alert')).toHaveTextContent('无法绑定');
  expect(api).not.toHaveBeenCalled();
});

it('displays typed values and follows a relation within the same explicit package',async()=>{
  metadata();
  vi.mocked(post).mockResolvedValueOnce(page('p1',[{iri:'urn:inspection'}])).mockResolvedValueOnce(page('p1',[
    {predicate:'urn:note',object:{term_type:'LITERAL',value:'Synthetic note',datatype:'urn:string',language:'en'}},
    {predicate:'urn:inspectedTree',object:{term_type:'IRI',value:'urn:tree'}}])).mockResolvedValueOnce(page('p1',[]));
  mount(<ObjectBrowser packages={[{package_id:'p1'}]} releases={[]}/>);
  fireEvent.change(screen.getByLabelText('本体包版本'),{target:{value:'p1'}});
  fireEvent.change(screen.getByLabelText('实例所属 Class IRI'),{target:{value:'urn:Inspection'}});
  fireEvent.click(screen.getByRole('button',{name:'查询实例'}));
  fireEvent.click(await screen.findByRole('button',{name:'查看属性与关系 urn:inspection'}));
  expect(await screen.findByText('Synthetic note')).toBeInTheDocument();
  expect(screen.getByText('urn:string')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'浏览关联对象 urn:tree'}));
  await waitFor(()=>expect(post).toHaveBeenLastCalledWith('/projects/project-1/objects/query',{package_id:'p1',release_id:null,instance_iri:'urn:tree',offset:0,limit:100}));
});

it('ignores a late object result after the selected package changes',async()=>{
  metadata();
  let resolve!:(value:unknown)=>void;
  vi.mocked(post).mockImplementationOnce(<T,>()=>new Promise<T>(done=>{resolve=value=>done(value as T);}));
  mount(<ObjectBrowser packages={[{package_id:'p1'},{package_id:'p2'}]} releases={[]}/>);
  fireEvent.change(screen.getByLabelText('本体包版本'),{target:{value:'p1'}});
  fireEvent.change(screen.getByLabelText('实例所属 Class IRI'),{target:{value:'urn:Class'}});
  fireEvent.click(screen.getByRole('button',{name:'查询实例'}));
  fireEvent.change(screen.getByLabelText('本体包版本'),{target:{value:'p2'}});
  await act(async()=>resolve(page('p1',[{iri:'urn:stale-result'}])));
  expect(screen.queryByText('urn:stale-result')).not.toBeInTheDocument();
});

it('fetches the next bounded metadata page instead of hiding terms after the first hundred',async()=>{
  metadata();mount(<ObjectBrowser packages={[{package_id:'p1'}]} releases={[]}/>);
  fireEvent.change(screen.getByLabelText('本体包版本'),{target:{value:'p1'}});
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'读取锁定术语与定义'}));
  fireEvent.click(await screen.findByRole('button',{name:'下一批术语'}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith('/projects/project-1/metadata?package_id=p1&offset=100&limit=100',expect.any(Object)));
});
