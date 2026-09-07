import {afterEach,describe,expect,it} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {DataTable,Field} from './components';

afterEach(cleanup);
describe('working surfaces',()=>{
 it('paginates 1000 actual component records without 1000 DOM rows',()=>{
  render(<DataTable data={Array.from({length:1000},(_,i)=>({id:`record-${i}`}))} fields={[["id","记录"]]}/>);
  expect(screen.getAllByRole('row')).toHaveLength(26);
  expect(screen.getByText('1 / 40 · 1000 条')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'下一页'}));
  expect(screen.getByText('record-25')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('搜索表格'),{target:{value:'record-999'}});
  expect(screen.getByText('record-999')).toBeInTheDocument();
  expect(screen.getAllByRole('row')).toHaveLength(2);
 });
 it('associates controls with explicit accessible labels',()=>{
  render(<Field label="明确表单标签"><select><option>值</option></select></Field>);
  expect(screen.getByLabelText('明确表单标签')).toHaveAttribute('id');
 });
 it('renders untrusted markup as text',()=>{
  const {container}=render(<DataTable data={[{text:'<script>alert(1)</script>'}]} fields={[["text","原文"]]}/>);
  expect(container.querySelector('script')).toBeNull();
  expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument();
 });
});
