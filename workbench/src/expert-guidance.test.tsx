import {afterEach, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {MemoryRouter, Outlet, Route, Routes} from 'react-router-dom';
import {ExpertGuidance} from './expert-guidance';
import {type WorkspaceContext} from './shell';

afterEach(cleanup);
function setup(permissions:string[]) {
  const submit=vi.fn().mockResolvedValue(undefined);
  const context={principal:{principal_id:'synthetic',principal_type:'HUMAN',permissions},prefix:'/projects/synthetic',busy:false,submit,
    state:{project:{project_id:'synthetic'},results:[],jobs:[],modeling_session:{session_id:'s',revision:7,expert:{enabled:true,loops:[],stages:{'1':{
      version:0,digest:'frozen-config',status:'DRAFT',confirmed_by:null,origin:'DEFAULT_TEMPLATE_NOT_EXPERT_CONFIRMED',
      configuration:{stage:1,pre_guidance_prompt:'synthetic pre',post_review_prompt:'synthetic post',criteria:[{criterion_id:'s1',required:true}],budget:{max_revision_rounds:3},method_overrides:{}}}}}}}} as unknown as WorkspaceContext;
  render(<MemoryRouter><Routes><Route element={<Outlet context={context}/>}><Route index element={<ExpertGuidance stage={1}/>}/></Route></Routes></MemoryRouter>);
  fireEvent.click(screen.getByText(/专家指导 · S1/));
  return submit;
}
it('shows unconfirmed defaults and sends a version-bound confirmation, never approval',()=>{
  const submit=setup(['*']);
  expect(screen.getByText(/默认模板待专家确认/)).toBeVisible();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button',{name:'保存并确认指导（新版本）'}));
  expect(submit).toHaveBeenCalledWith('/toolchain/modeling.expert.save',expect.objectContaining({expected_revision:7,expected_configuration_digest:'frozen-config',confirm:true}));
  expect(screen.queryByRole('button',{name:'自动批准'})).not.toBeInTheDocument();
});
it('disables configuration writes without existing reviewer permissions',()=>{
  setup(['model:propose','source:read']);
  expect(screen.getByRole('button',{name:'保存并确认指导（新版本）'})).toBeDisabled();
  expect(screen.getByLabelText('生成前专家指导')).toBeDisabled();
});
