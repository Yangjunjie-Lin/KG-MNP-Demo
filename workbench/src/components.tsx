import { cloneElement, isValidElement, useId, useMemo, useState, type ReactElement, type ReactNode } from 'react';
import { flexRender, getCoreRowModel, getPaginationRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table';
import { str, type Document } from './api';

export function Field({label, children}: {label: string; children: ReactNode}) { const id=useId(); return <div className="field"><label htmlFor={id}>{label}</label>{isValidElement(children)?cloneElement(children as ReactElement<{id:string}>,{id}):children}</div>; }
export function Panel({title, children}: {title: string; children: ReactNode}) { return <section className="panel"><h2>{title}</h2>{children}</section>; }
export function Id({value}: {value: unknown}) { return <code title={str(value)}>{str(value)}</code>; }
export function Status({value}: {value: unknown}) { return <span className="status">{str(value)}</span>; }
export function PackageDownload({projectId, packageId, allowed}: {projectId: string; packageId: string; allowed: boolean}) {
  if (!allowed) return <p className="muted">下载本体包需要 package:export 权限。</p>;
  return <p><a download="ontology.kgop" href={`/api/v1/projects/${encodeURIComponent(projectId)}/packages/${encodeURIComponent(packageId)}/archive`}>下载已验证本体包（.kgop）</a></p>;
}
export function SelectDocument({label, items, idKey, value, onChange}: {label: string; items: Document[]; idKey: string; value: string; onChange: (v: string) => void}) {
  return <Field label={label}><select required value={value} onChange={e => onChange(e.target.value)}><option value="">请选择</option>{items.map(item => <option key={str(item[idKey])} value={str(item[idKey])}>{str(item[idKey])}</option>)}</select></Field>;
}
export function DataTable({data, fields}: {data: Document[]; fields: [string, string][]}) {
  const [search, setSearch] = useState(''); const id = useId();
  const columns = useMemo<ColumnDef<Document>[]>(() => fields.map(([key, name]) => ({accessorKey: key, header: name, cell: info => <span>{str(info.getValue())}</span>})), [fields]);
  const filtered = useMemo(() => data.filter(row => fields.some(([key]) => str(row[key]).toLowerCase().includes(search.toLowerCase()))), [data, fields, search]);
  const table = useReactTable({data: filtered, columns, getCoreRowModel: getCoreRowModel(), getPaginationRowModel: getPaginationRowModel(), initialState: {pagination: {pageSize: 25}}});
  return <><label className="search" htmlFor={id}>搜索表格<input id={id} value={search} onChange={e => {setSearch(e.target.value); table.setPageIndex(0);}} /></label><div className="table-scroll" tabIndex={0} role="region" aria-label="数据表格（可横向滚动）"><table><thead>{table.getHeaderGroups().map(group => <tr key={group.id}>{group.headers.map(h => <th key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map(row => <tr key={row.id}>{row.getVisibleCells().map(cell => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody></table></div>{!filtered.length && <p className="empty">没有匹配记录</p>}<div className="pager"><button type="button" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>上一页</button><span>{table.getState().pagination.pageIndex + 1} / {Math.max(1, table.getPageCount())} · {filtered.length} 条</span><button type="button" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>下一页</button></div></>;
}
