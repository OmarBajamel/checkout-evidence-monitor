import {useResource} from '../api/client';
import {Button} from '../components/ui/button';
import type {EvidenceDetail} from '../api/types';
import {CopyText,ExportControl,FindingList,Notice,PageTitle,ProfileDetails,ResourceState,Status} from '../components/common';

export function EvidencePanel({id,standalone=false}:{id:string;standalone?:boolean}){
 const r=useResource<EvidenceDetail>(id?'/api/v1/evidence/'+encodeURIComponent(id):null);
 if(!id)return <div className="evidence-empty"><span className="eyebrow">Follow the evidence</span><h2>Select a change</h2><p>Its originating state, body representation and limitations will appear here.</p></div>;
 return <section aria-label="Supporting evidence" className={standalone?'':'evidence-panel'}><ResourceState {...r}>{r.data&&<EvidenceContent data={r.data}/>}</ResourceState></section>;
}
export function EvidenceContent({data}:{data:EvidenceDetail}){
 const e=data.record;
 return <><div className="panel-heading"><span className="eyebrow">{e.kind} · {e.state}</span><Status value={data.run_status}/></div><h2 className="resource-heading">{e.url_display||'Metadata record'}</h2>
 <div className="inline-meta"><Status value={data.provenance}/><Status value={data.integrity.state}/></div>
 <p className="muted">Integrity refers to stored sanitized bytes, not server authenticity.</p>
 <dl className="metadata-grid">{[['Observed',e.observed_at],['Origin',e.origin||'Unavailable'],['Frame / step',e.frame_id+' / '+e.step_id],['Reference',e.reference_observed?'Observed':'Not observed'],['Request',e.request_observed?'Observed':'Not observed'],['Response',e.response_observed?'Observed':'Not observed'],['Execution','Not measured'],['Body representation',e.body_representation||e.body_reason||'Unavailable'],['SHA-256',e.body_sha256||'No captured hash'],['TLS validation',e.tls_validation],['Delivery',e.delivery],['Relationship',e.relation]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
 {!e.body_sha256&&<Notice title="Body evidence unavailable"><p>{e.body_reason}. A missing body does not mean the script was unchanged.</p></Notice>}
 <details className="record-preview"><summary>Sanitized record preview</summary><pre>{data.preview}</pre>{data.preview_truncated&&<p>Preview limited to 16 KiB of {data.preview_total_bytes} bytes.</p>}<CopyText text={data.preview}/></details>
 <ProfileDetails profile={data.profile}/><FindingList findings={data.findings}/><ExportControl id={data.run_id}/></>;
}
export default function Evidence({id,search,navigate}:{id:string;search:string;navigate:(path:string)=>void}){
 const back=new URLSearchParams(search).get('back');
 return <><PageTitle eyebrow="04 / Source record" title="Evidence" description="Read the observation, its provenance and what it cannot establish."/>
 {back&&back.startsWith('/changes?')&&<Button variant="outline" onClick={()=>navigate(back)}>Back to comparison</Button>}
 {id?<EvidencePanel id={id} standalone/>:<Notice title="Choose a recorded observation"><p>Open an evidence link from Journey or select a change in Changes.</p></Notice>}</>;
}
