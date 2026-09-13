import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {api} from './api';
import {OntologyIOEvaluation} from './ontology-io';

vi.mock('./shell',()=>({useWorkspace:()=>({state:{project:{project_id:'project-1'}},prefix:'/projects/project-1'})}));
vi.mock('./api',async importOriginal=>({...await importOriginal<typeof import('./api')>(),api:vi.fn()}));
afterEach(cleanup);
beforeEach(()=>{vi.mocked(api).mockReset();});
function show(){render(<MemoryRouter><OntologyIOEvaluation/></MemoryRouter>);}
function upload(value:unknown){
  const file=new File([JSON.stringify(value)],'report.json',{type:'application/json'});
  Object.defineProperty(file,'text',{value:async()=>JSON.stringify(value)});
  fireEvent.change(screen.getByLabelText('研究报告 JSON'),{target:{files:[file]}});
}

describe('independent ontology I/O reports',()=>{
  it('defaults to not-run and does not contact a model or fabricate a score',()=>{
    show();expect(screen.getByText('NOT_RUN',{exact:true})).toBeVisible();
    expect(screen.getByText(/指标为 null/)).toBeVisible();expect(api).not.toHaveBeenCalled();
  });
  it('uses the actual flat API contract and preserves legitimate zero separately from unscorable',async()=>{
    const report={status:'UNSCORABLE',metrics:[
      {name:'edge_f1',value:0,status:'MEASURED',unit:'fraction'},
      {name:'graph_similarity',value:null,status:'UNSCORABLE',unit:'fraction'},
    ],sample_count:2,failure_count:1,resources:[],limitations:[]};
    vi.mocked(api).mockResolvedValue({payload:{report,source_authenticity:'UNVERIFIED_EXTERNAL_REPORT',validation:'REPORT_SCHEMA_ONLY'}});
    show();upload(report);
    await waitFor(()=>expect(screen.getByText('null / UNSCORABLE')).toBeVisible());
    expect(screen.getByText('0',{exact:true})).toBeVisible();
    expect(api).toHaveBeenCalledExactlyOnceWith('/operations/ontology.io.inspect',expect.objectContaining({method:'POST',body:JSON.stringify({project_id:'project-1',report})}));
    expect(screen.getByText(/UNVERIFIED_EXTERNAL_REPORT/)).toBeVisible();
  });
  it('displays server rejection without retaining the rejected report',async()=>{
    vi.mocked(api).mockRejectedValue(new Error('Research report rejected'));
    show();upload({private_gold:'must not display'});
    await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Research report rejected'));
    expect(screen.queryByText('must not display')).not.toBeInTheDocument();
  });
});
