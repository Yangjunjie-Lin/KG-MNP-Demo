// Synthetic component tests, not service execution or semantic verification.
import {afterEach, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {ArtifactViewer, StepDetail, Stepper, ValidationSummary, type Method, type MethodRegistry} from './modeling-components';

afterEach(cleanup);
const method:Method={method_id:'1.1',stage:1,title:'核验输入与质量',full_name:'输入契约检查与质量分流',roles:['program'],source_definition:'先核验结构与来源。',guard:'缺失依据不得建模。',source_implementation:[{name:'Pydantic',use:'核验',how:'严格字符串类型'}],required_output:'输入检查报告',tutorial_file:'tutorial/stages/1.1.json',tutorial_inputs:['B0']};
it('uses registry labels and reports progress without completion claims',()=>{
  const registry={stages:[{id:1,title:'输入核验与范围确认',summary:'核验输入'}],methods:[method]} as MethodRegistry;
  render(<MemoryRouter><Stepper registry={registry} step={method} href={id=>'?step='+id}/></MemoryRouter>);
  expect(screen.getByRole('link')).toHaveAttribute('href','/?step=1.1');
  expect(screen.getByText('尚未核定执行进度')).toBeInTheDocument();
});
it('provides keyboard-operable ARIA tabs and a visible method boundary',()=>{
  const change=vi.fn();
  render(<StepDetail method={method} view="method" onView={change}><p>operation</p></StepDetail>);
  expect(screen.getByRole('tab',{name:'方法说明'})).toHaveAttribute('aria-selected','true');
  fireEvent.keyDown(screen.getByRole('tablist'),{key:'Home'});
  expect(change).toHaveBeenCalledWith('operation');
  expect(screen.getByText(/缺失依据不得建模/)).toBeInTheDocument();
});
it('renders specific facts and invokes the same evidence target without auto review',()=>{
  const open=vi.fn(), fact={fact_id:'F-004',subject:'E-001',predicate:'belongsToDepartment',object:{kind:'iri',value:'D-01'},evidence_refs:['record','text']};
  render(<ArtifactViewer value={{facts:[fact]}} onEvidence={open}/>);
  expect(screen.getByText('IRI：D-01')).toBeInTheDocument();
  expect(screen.getByText('record；text')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'查看 F-004 的证据'}));
  expect(open).toHaveBeenCalledWith(fact);
  expect(screen.getByText('完整 JSON／原始内容').closest('details')).not.toHaveAttribute('open');
});
it('does not hide a failed or absent check behind a positive summary',()=>{
  const {rerender}=render(<ValidationSummary checks={[]}/>);
  expect(screen.getByText(/NOT_RUN/)).toBeInTheDocument();
  rerender(<ValidationSummary checks={[{name:'OWL',status:'TIMEOUT',reason:'工具超时，不能交付'}]}/>);
  expect(screen.getByText('TIMEOUT')).toBeInTheDocument();
  expect(screen.getByText('工具超时，不能交付')).toBeInTheDocument();
});
