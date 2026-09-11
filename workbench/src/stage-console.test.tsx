import {describe,it,expect} from 'vitest';
import {render,screen,fireEvent} from '@testing-library/react';
import {ComparisonTable,stages,summarize} from './stage-console';

describe('five-stage console',()=>{
  it('exposes only five aggregate stages',()=>{
    expect(stages).toHaveLength(5);
    expect(stages[4][0]).toBe('语义编译与交付验收');
    expect(stages.flat().join(' ')).not.toMatch(/1\.1|教程/);
  });
  it('keeps no-result states empty and calculates real output changes',()=>{
    expect(summarize({})).toEqual([]);
    expect(summarize({fields:[{field:'name',examples:['甲']},{field:'id',examples:['001']}]})).toHaveLength(2);
    expect(summarize({fields:[{field:'name',examples:['甲']}]})).toHaveLength(1);
  });
  it('shows representative rows and can reveal every error item',()=>{
    const data=Array.from({length:8},(_,i)=>({name:`对象${i}`,change:i===7?'FAIL':'PASS',value:i}));
    render(<ComparisonTable data={data} onDetail={()=>{}}/>);
    expect(screen.getByText(/显示 5 \/ 总共 8/)).toBeVisible();
    fireEvent.click(screen.getByRole('button',{name:'展开全部（含问题项）'}));
    expect(screen.getByText('FAIL')).toBeVisible();
    expect(screen.getByText(/显示 8 \/ 总共 8/)).toBeVisible();
  });
});
