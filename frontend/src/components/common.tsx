import {useEffect,useId,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {AlertTriangle,ArrowDownToLine,ArrowUpRight,Check,Copy,LoaderCircle,MinusCircle,Circle} from 'lucide-react';
import {Button} from './ui/button';
import {exportRun} from '../api/client';
import type {Profile,Finding,Run} from '../api/types';

export function Status({value}:{value:string}){
 const tone=/FAILED|ERROR|MISMATCH|BLOCKED|INCOMPATIBLE|MISSING|EXPIRED/.test(value)?'danger':/PARTIAL|INCONCLUSIVE|AMBIGUOUS|UNOBSERVABLE|UNKNOWN|NOT_RUN|DECLARED|INTERRUPTED|OFFLINE|DEFERRED|INVESTIGATE/.test(value)?'caution':/^(COMPLETED|REACHED|COMPARABLE|VERIFIED_SANITIZED_BYTES|READY|ACTIVE)$/.test(value)?'positive':'neutral';
 const Icon=tone==='danger'?MinusCircle:tone==='caution'?AlertTriangle:tone==='positive'?Check:Circle;
 return <span className={'status '+tone}><Icon size={13} aria-hidden/>{value.replaceAll('_',' ')}</span>;
}
export function Notice({title,children,tone='caution'}:{title:string;children:ReactNode;tone?:string}){
 return <div className={'notice '+tone} role={tone==='danger'?'alert':'status'}><strong>{title}</strong><div>{children}</div></div>;
}
export function ResourceState({loading,error,retry,empty,children}:{loading:boolean;error:Error|null;retry:()=>void;empty?:boolean;children:ReactNode}){
 if(loading)return <div className="state-message" role="status"><LoaderCircle className="loading-icon" size={20}/> Loading local records…</div>;
 if(error)return <Notice title="Local records unavailable" tone="danger"><p>{error.message}</p><Button variant="outline" onClick={retry}>Retry request</Button></Notice>;
 if(empty)return <div className="state-message"><h2>No recorded evidence yet</h2><p>Set up an authorized store in Monitoring, import a sanitized CEM JSON record, or use the isolated synthetic LAB. Opening this workbench never starts collection.</p></div>;
 return <>{children}</>;
}
export function ProfileDetails({profile}:{profile:Profile}){
 return <details className="profile-details"><summary>Observation profile <span>{profile.mode} · {profile.consent} · Chromium {profile.browser_version}</span></summary><dl className="metadata-grid">
 {Object.entries(profile).map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{typeof value==='object'?JSON.stringify(value):value}</dd></div>)}</dl></details>;
}
export function RunSelect({label,value,onChange,runs}:{label:string;value:string;onChange:(v:string)=>void;runs:Run[]}){
 const selectId=useId();
 const [query,setQuery]=useState('');
 const filtered=runs.filter(r=>(r.label+' '+r.id).toLowerCase().includes(query.toLowerCase()));
 return <div className="field"><label className="field"><span>Filter {label.toLowerCase()} runs</span><input aria-label={'Filter '+label.toLowerCase()+' runs'} value={query} onChange={e=>setQuery(e.target.value)} type="search"/></label><div className="field"><label className="field-label" htmlFor={selectId}>{label}</label><select id={selectId} value={value} onChange={e=>onChange(e.target.value)}><option value="">Choose a recorded run</option>{value&&!filtered.some(r=>r.id===value)&&<option value={value}>{runs.find(r=>r.id===value)?.label||value} · selected</option>}{filtered.map(r=><option key={r.id} value={r.id}>{r.label} · {r.started_at.slice(0,16)} UTC</option>)}</select></div></div>;
}
export function ExportControl({id}:{id:string}){
 const [format,setFormat]=useState('html'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[feedback,setFeedback]=useState('');
 async function save(){setBusy(true);setError('');setFeedback('');try{await exportRun(id,format);setFeedback('Report prepared for download.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <div><div className="export-control"><select aria-label="Report format" value={format} onChange={e=>setFormat(e.target.value)}><option value="html">Offline HTML</option><option value="json">JSON evidence</option><option value="csv">CSV observations</option></select><Button variant="outline" disabled={busy} onClick={save}><ArrowDownToLine size={16}/>{busy?'Preparing…':'Export report'}</Button></div>{error&&<p role="alert" className="error-text">{error}</p>}{feedback&&<p className="muted" role="status">{feedback}</p>}</div>;
}
export function FindingList({findings}:{findings:Finding[]}){
 return <div className="finding-list">{findings.map(f=><article key={f.id}><div className="eyebrow">{f.rule_ids.join(' / ')}</div><h3>{f.title}</h3><div className="inline-meta"><Status value={f.condition}/><span>Evidence: {f.evidence_sufficiency.toLowerCase()}</span><span>Applicability: {f.applicability.toLowerCase()}</span><span>Confidence: {f.confidence.toLowerCase()}</span></div><p>{f.interpretation}</p><p className="muted">Suggested reviewer: {f.suggested_owner}</p>{f.evidence_ids.map(id=><Button key={id} variant="ghost" size="small" onClick={()=>{history.pushState(null,'','/evidence/'+encodeURIComponent(id));window.dispatchEvent(new PopStateEvent('popstate'));}}>View evidence {id.slice(0,8)}</Button>)}{f.mappings.map(m=><details key={m.standard+m.id}><summary>{m.standard} {m.id} · {m.relationship.replaceAll('_',' ').toLowerCase()}</summary><p>{m.limitation}</p><a href={m.url} rel="noreferrer" target="_blank">Official source (external) <ArrowUpRight size={12}/></a></details>)}</article>)}</div>;
}
export function CopyText({text}:{text:string}){
 const [message,setMessage]=useState('');
 async function copy(){try{await navigator.clipboard.writeText(text);setMessage('Sanitized text copied.');}catch{setMessage('Copy unavailable. Select the text manually.');}}
 return <div className="copy-control"><Button variant="ghost" onClick={copy}><Copy size={15}/>Copy sanitized text</Button><span role="status">{message}</span></div>;
}
export function Dialog({open,onClose,title,children}:{open:boolean;onClose:()=>void;title:string;children:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null),previous=useRef<HTMLElement|null>(null),titleId=useId();
 useEffect(()=>{if(open){previous.current=document.activeElement as HTMLElement;ref.current?.showModal();}else {ref.current?.close();previous.current?.focus();}},[open]);
 return <dialog ref={ref} aria-labelledby={titleId} onCancel={event=>{event.preventDefault();onClose();}} onClose={onClose}><h2 id={titleId}>{title}</h2>{children}</dialog>;
}
export function PageTitle({eyebrow,title,description,children}:{eyebrow:string;title:string;description:string;children?:ReactNode}){
 return <header className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1 tabIndex={-1}>{title}</h1><p>{description}</p></div>{children}</header>;
}
