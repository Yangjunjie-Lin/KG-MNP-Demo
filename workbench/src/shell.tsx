import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { api, ApiError, clearIdentity, post, queryClient, requestKeys, setCsrf, type Pack, type Principal, type Project, type ProjectState } from './api';
import { Field, Panel, Status } from './components';
import { Sources } from './sources';
const Modeling = lazy(()=>import('./five-stage-modeling').then(module=>({default:module.FiveStageModeling})));
import {FeedbackEvolution, TaskExecution, ModuleEvaluation, ServiceDetails} from './toolchain-modules';
import { Releases } from './releases';
import { Versions } from './versions';
import { Integrations } from './integrations';
import {Jobs} from './jobs';
import {ProjectOverview as Overview} from './project-overview';

export type WorkspaceContext = {state: ProjectState; principal: Principal; prefix: string; busy: boolean; submit: (path: string, body: unknown) => Promise<void>};
export function useWorkspace() { return useOutletContext<WorkspaceContext>(); }
function Login({onLogin}: {onLogin: () => void}) {
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function login(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); setError(''); const form = event.currentTarget; const credential = String(new FormData(form).get('credential'));
    try { const result = await api<{csrf_token: string}>('/session', {method: 'POST', headers: {Authorization: `Bearer ${credential}`}}); form.reset(); clearIdentity(); setCsrf(result.csrf_token); onLogin(); }
    catch (err) {form.reset(); setError(String(err));} finally {setBusy(false);} }
  return <main className="login"><div className="brand">知构工具链 <span>ZhiGou Toolchain</span></div><Panel title="登录本体工程工作台"><p>使用本地管理员签发的凭证。此页面不提供管理员注册。</p><form onSubmit={login} onInvalid={event=>{event.preventDefault();setError('请填写访问凭证。');(event.target as HTMLInputElement).focus();}}><Field label="访问凭证"><input name="credential" aria-describedby={error?'login-error':undefined} aria-invalid={!!error} type="password" autoComplete="off" required /></Field><button disabled={busy}>登录</button></form>{error && <p id="login-error" role="alert" className="error">{error}</p>}<p className="muted">长期凭证不会保存到浏览器存储。后台任务由当前服务器授权控制。</p></Panel></main>;
}
export function App() {
  const [expired,setExpired]=useState(false);
  useEffect(()=>{const onExpired=()=>setExpired(true);window.addEventListener('zhigou-session-expired',onExpired);return()=>window.removeEventListener('zhigou-session-expired',onExpired);},[]);
  const session = useQuery({queryKey: ['session'], queryFn: ({signal}) => api<{principal: Principal; csrf_token: string}>('/session', {signal}), refetchInterval: query => query.state.data ? 30000 : false, refetchOnWindowFocus: query => !!query.state.data, refetchOnReconnect: query => !!query.state.data});
  useEffect(() => {if (session.data) setCsrf(session.data.csrf_token);}, [session.data]);
  if (session.isPending) return <main className="login" role="status">正在检查会话…</main>;
  if (!session.data || session.isError || expired) return <><p className="notice">会话到期后暂停新写入。重新认证将保留当前入口并读取原任务收据，不自动重放业务动作。</p><Login onLogin={() => {setExpired(false); session.refetch();}} /></>;
  return <Routes><Route path="/" element={<Projects principal={session.data.principal} />} /><Route path="/projects/:projectId" element={<Workspace principal={session.data.principal} />}><Route index element={<Navigate to="overview" replace />} /><Route path="overview" element={<Overview />} /><Route path="sources" element={<><Sources /><ModuleEvaluation module="ingestion"/></>} /><Route path="modeling" element={<Suspense fallback={<p role="status">正在加载建模视图…</p>}><Modeling /></Suspense>} /><Route path="modeling/tutorial/employee-department" element={<LegacyTutorialRedirect/>} /><Route path="releases" element={<><Releases /><ModuleEvaluation module="ontology"/><ServiceDetails/></>} /><Route path="versions" element={<Versions />} /><Route path="integrations" element={<Integrations />} /><Route path="execution" element={<TaskExecution />} /><Route path="evolution" element={<FeedbackEvolution />} /><Route path="jobs" element={<Jobs />} /></Route><Route path="*" element={<main className="login"><h1>页面不存在</h1><Link to="/">返回项目选择</Link></main>} /></Routes>;
}
function LegacyTutorialRedirect(){const {projectId=""}=useParams();return <Navigate to={`/projects/${encodeURIComponent(projectId)}/modeling?stage=1`} replace/>;}
async function logout() { try { await post('/session/logout', {}); } finally {clearIdentity(); window.location.assign('/');} }
function Projects({principal}: {principal: Principal}) {
  const navigate = useNavigate(); const [error, setError] = useState('');
  const projects = useQuery({queryKey: ['projects', principal.principal_id], queryFn: () => api<{projects: Project[]}>('/projects')});
  const packs = useQuery({queryKey: ['packs', principal.principal_id], queryFn: () => api<{domain_packs: Pack[]}>('/domain-packs')});
  async function create(event: FormEvent<HTMLFormElement>) {event.preventDefault(); const form = new FormData(event.currentTarget); const [domain_pack, domain_pack_version] = String(form.get('pack')).split('@'); setError(''); try { const project = await post<Project>('/projects', {name: form.get('name'), domain_pack, domain_pack_version}); navigate(`/projects/${encodeURIComponent(project.project_id)}/overview`); } catch(err) {setError(String(err));} }
  return <main className="projects"><header className="top"><div className="brand">知构工具链 <span>本体工程工作台</span></div><span>{principal.principal_id}</span><button onClick={logout}>退出</button></header><h1>选择项目</h1><p className="muted">项目绑定明确的领域包版本，资料、审核和本体包相互隔离。</p>{(projects.error || packs.error || error) && <p role="alert" className="error">{String(projects.error || packs.error || error)}</p>}<div className="project-grid"><Panel title="已有项目">{projects.isPending ? <p role="status">正在读取…</p> : !projects.data?.projects.length ? <p className="empty">暂无可访问项目</p> : projects.data.projects.map(p => <Link className="project-card" key={p.project_id} to={`/projects/${encodeURIComponent(p.project_id)}/overview`}><strong>{p.project_name}</strong><span>{p.domain_pack} · {p.domain_pack_version}</span><Status value={p.status} /></Link>)}</Panel><Panel title="创建项目"><form onSubmit={create}><Field label="项目名称"><input name="name" required maxLength={200} /></Field><Field label="领域包与版本"><select name="pack" required defaultValue=""><option value="">请选择领域包</option>{packs.data?.domain_packs.map(p => <option key={`${p.pack_id}@${p.pack_version}`} value={`${p.pack_id}@${p.pack_version}`} disabled={p.availability !== 'AVAILABLE'}>{p.display_name || p.pack_id} · {p.pack_version} · {p.lifecycle}</option>)}</select></Field><button>创建项目</button></form></Panel></div></main>;
}
function Workspace({principal}: {principal: Principal}) {
  const {projectId = ''} = useParams(); const prefix = `/projects/${encodeURIComponent(projectId)}`; const [collapsed, collapse] = useState(false); const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false); const keys = useRef(requestKeys);
  const state = useQuery({queryKey: ['state', principal.principal_id, projectId], queryFn: ({signal}) => api<ProjectState>(`${prefix}/state`, {signal}), refetchInterval: 2000});
  useEffect(() => {setMessage(''); return () => {queryClient.removeQueries({predicate:q=>q.queryKey.includes(projectId)});};}, [projectId, principal.principal_id]);
  useEffect(() => {if (state.error instanceof ApiError && state.error.status === 401) clearIdentity();}, [state.error]);
  async function submit(path: string, body: unknown) {const signature = principal.principal_id + prefix + path + JSON.stringify(body); const key = keys.current.get(signature) || crypto.randomUUID(); keys.current.set(signature,key); setBusy(true); setMessage(''); try {const result = await post<{job_id?: string}>(prefix + path, body,key); setMessage(result.job_id ? `任务已提交：${result.job_id}。请查看任务中心；关闭页面不会取消任务。` : '操作已完成'); await queryClient.invalidateQueries({queryKey: ['state']});} catch(err) {setMessage(String(err));} finally {setBusy(false);} }
  const navigation = [['sources','数据接入与规则化'],['modeling','本体建模'],['releases','本体服务与版本管理'],['execution','任务规划与业务执行'],['evolution','反馈评估与演进']];
  return <div className={`workspace ${collapsed ? 'collapsed' : ''} ${window.location.search.includes('focus=1') ? 'focused' : ''}`}><aside><div className="brand">知构工具链</div><button aria-expanded={!collapsed} onClick={() => collapse(!collapsed)}>{collapsed ? '展开导航' : '收起导航'}</button><nav aria-label="工作台导航">{navigation.map(([path,label]) => <NavLink key={path} to={`${prefix}/${path}`}>{label}</NavLink>)}</nav><Link to="/">切换项目</Link></aside><div className="workspace-main"><header className="top"><strong>{state.data?.project.project_name || '项目工作台'}</strong><span>{principal.principal_id} · {principal.principal_type}</span><Link to={`${prefix}/jobs`}>运行记录</Link><Link to={`${prefix}/overview`}>项目</Link><button onClick={logout}>退出</button></header><main><p className="notice">预发布版本 · 本地发布与环境选择不会自动部署到外部系统。请使用明确版本并逐项审核。</p>{message && <p role="status" className="notice">{message}</p>}{state.error ? <p role="alert" className="error">读取失败：{String(state.error)}<button onClick={() => state.refetch()}>重试读取</button></p> : state.data ? <Outlet context={{state: state.data, principal, prefix, busy, submit} satisfies WorkspaceContext} /> : <p role="status">正在读取项目状态…</p>}</main></div></div>;
}
