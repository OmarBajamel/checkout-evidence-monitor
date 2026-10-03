import {ArrowLeft} from 'lucide-react';
import {useResource} from '../api/client';
import {Button} from '../components/ui/button';
import type {EvidenceDetail} from '../api/types';
import {CopyText,ExportControl,FindingList,Notice,PageTitle,ProfileDetails,ResourceState,Status} from '../components/common';

export function EvidencePanel({id,standalone=false}:{id:string;standalone?:boolean}){
 const r=useResource<EvidenceDetail>(id?'/api/v1/evidence/'+encodeURIComponent(id):null);
 if(!id)return <div className="evidence-empty"><span className="eyebrow">Follow the evidence</span><h2>Select a change</h2><p>Its observation context and limits appear here.</p></div>;
 return <section aria-label="Supporting evidence" className={standalone?'':'evidence-panel'}><ResourceState {...r}>{r.data&&<EvidenceContent data={r.data}/>}</ResourceState></section>;
}
export function EvidenceContent({data}:{data:EvidenceDetail}){
 const e=data.record;
 return <><div className="evidence-hero"><div className="panel-heading"><span className="eyebrow">{e.kind} · {e.state}</span><Status value={data.provenance}/></div><h2 className="resource-heading">{e.url_display||'Metadata record'}</h2><p>{data.run_id} / {e.step_id} / {e.frame_id}</p></div>
 <div className="inspector-layout"><section className="surface"><h2>Observed record</h2><p className="muted">Reference, request and response are separate layers. Execution is not measured.</p><dl className="metadata-grid">
 {[['Evidence ID',e.id],['Resource identity',e.identity],['Observed',e.observed_at],['Origin',e.origin||'Unavailable'],['Frame / step',e.frame_id+' / '+e.step_id],['Run status',data.run_status],['Reference',e.reference_observed?'Observed':'Not observed'],['Request',e.request_observed?'Observed':'Not observed'],['Response / method',(e.http_status||'Not observed')+' / '+e.method],['Execution','Not measured'],['Body representation',e.body_representation||e.body_reason||'Unavailable'],['Body size',e.body_size===null?'Unavailable':e.body_size.toLocaleString()+' bytes'],['SHA-256',e.body_sha256||'No captured hash'],['TLS validation',e.tls_validation],['Delivery / relationship',e.delivery+' / '+e.relation],['Cache / service worker',String(e.from_cache)+' / '+String(e.from_service_worker)],['Redirected from',e.redirected_from||'None recorded'],['Integrity attribute',e.integrity_metadata||'None observed']].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
 {!e.body_sha256&&<Notice title="Body evidence unavailable"><p>{e.body_reason}. A missing body does not mean the script was unchanged.</p></Notice>}
 <details><summary>Retained response headers</summary>{Object.keys(e.headers).length?<dl className="metadata-grid">{Object.entries(e.headers).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>:<p className="muted">No allowlisted headers retained.</p>}</details>
 <details className="record-preview"><summary>Sanitized record preview</summary><pre>{data.preview}</pre>{data.preview_truncated&&<p>Preview limited to 16 KiB of {data.preview_total_bytes} bytes.</p>}<CopyText text={data.preview}/></details></section>
 <aside className="inspector-context"><Notice title={data.integrity.state.replaceAll('_',' ')} tone={data.integrity.state==='VERIFIED_SANITIZED_BYTES'?'positive':'danger'}><p>Integrity refers to stored sanitized bytes, not server authenticity.</p></Notice><details className="surface"><summary>Inspect integrity details</summary><dl className="metadata-grid"><div><dt>Expected SHA-256</dt><dd>{data.integrity.expected_sha256}</dd></div><div><dt>Actual SHA-256</dt><dd>{data.integrity.actual_sha256||'Unavailable'}</dd></div></dl></details><ProfileDetails profile={data.profile}/><section className="surface"><h2>Observations requiring context</h2><FindingList findings={data.findings}/>{!data.findings.length&&<p className="muted">No scoped rule observations for this record.</p>}</section><ExportControl id={data.run_id}/></aside></div></>;
}
export default function Evidence({id,search,navigate}:{id:string;search:string;navigate:(path:string)=>void}){
 const back=new URLSearchParams(search).get('back');
 return <><PageTitle eyebrow="04 / Local evidence" title="Evidence, in full context." description="Read the observation, its provenance and what it cannot establish."/>
 {back&&back.startsWith('/changes?')&&<Button className="back-control" variant="outline" onClick={()=>navigate(back)}><ArrowLeft size={16}/>Back to comparison</Button>}
 {id?<EvidencePanel id={id} standalone/>:<Notice title="Choose a recorded observation" tone="info"><p>Open an evidence link from Journey or select a change in Changes.</p></Notice>}</>;
}
