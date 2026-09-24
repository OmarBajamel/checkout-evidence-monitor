import {useState} from 'react';
import {ArrowRight,ArrowUpRight} from 'lucide-react';
import {useResource} from '../api/client';
import type {Comparison,RunPage} from '../api/types';
import {Notice,PageTitle,ResourceState,RunSelect,Status,FindingList} from '../components/common';
import {Button} from '../components/ui/button';
import {EvidencePanel} from './Evidence';

export default function Changes({search,navigate}:{search:string;navigate:(path:string)=>void}){
 const params=new URLSearchParams(search),baseline=params.get('baseline')||'',candidate=params.get('candidate')||'';
 const runs=useResource<RunPage>('/api/v1/runs?limit=100');
 const result=useResource<Comparison>(baseline&&candidate?'/api/v1/comparisons?baseline='+baseline+'&candidate='+candidate:null);
 const filter=params.get('filter')||'ALL';
 const [selected,setSelected]=useState(params.get('selected')||'');
 function setFilter(value:string){const p=new URLSearchParams(search);p.set('filter',value);navigate('/changes?'+p.toString());}
 function selectEvidence(key:string){setSelected(key);const back=new URLSearchParams(search);back.set('selected',key);if(window.matchMedia('(max-width: 767px)').matches&&/^[a-f0-9]{32}$/.test(key))navigate('/evidence/'+key+'?back='+encodeURIComponent('/changes?'+back.toString()));}
 function change(which:string,value:string){const p=new URLSearchParams(search);p.set(which,value);setSelected('');navigate('/changes?'+p.toString());}
 const visible=result.data?.changes.filter(c=>filter==='ALL'||c.kind===filter)||[];
 const selection=visible.find(c=>(c.candidate_evidence_id||c.baseline_evidence_id||c.identity)===selected);
 const id=selection?.candidate_evidence_id||selection?.baseline_evidence_id||'';
 return <><PageTitle eyebrow="03 / Compare visits" title="Changes" description="A difference is a starting point. The evidence gives it context."/>
 <ResourceState loading={runs.loading} error={runs.error} retry={runs.retry}><div className="comparison-toolbar"><RunSelect label="Baseline" value={baseline} onChange={v=>change('baseline',v)} runs={runs.data?.items||[]}/><ArrowRight aria-hidden size={20}/><RunSelect label="Candidate" value={candidate} onChange={v=>change('candidate',v)} runs={runs.data?.items||[]}/></div>{runs.data&&runs.data.total>100&&<p className="muted">Showing the 100 most recent runs. Select older run IDs from Assessments.</p>}</ResourceState>
 {!baseline||!candidate?<Notice title="Choose two recorded visits"><p>Comparison uses the recorded profiles. A baseline choice is not a security approval.</p></Notice>:<ResourceState {...result}>{result.data&&(result.data.eligibility==='INCOMPATIBLE_PROFILE'?<Notice title="These visits are not comparable"><p>The following profile fields differ:</p><ul>{result.data.mismatch_fields.map(f=><li key={f}>{f.replaceAll('_',' ')}</li>)}</ul><Button variant="outline" onClick={()=>navigate('/runs/'+candidate+'/journey')}>Review candidate profile</Button></Notice>:<>
 <div className="comparison-summary"><Status value="COMPARABLE"/><span>Same declared observation profile. Missing evidence remains unknown.</span></div>
 <div className="filter-tabs" role="group" aria-label="Filter changes">{['ALL','ADDED','CHANGED','NOT_OBSERVED','AMBIGUOUS','UNOBSERVABLE'].map(f=><Button key={f} variant={filter===f?'default':'ghost'} size="small" aria-pressed={filter===f} onClick={()=>{setFilter(f);setSelected('');}}>{f.replaceAll('_',' ')}</Button>)}</div>
 <div className="change-layout"><section className="change-list" aria-label="Observed changes"><div className="section-label">{visible.length} displayed observations</div>{!visible.length?<div className="state-message"><h2>{filter==='ALL'?'No recorded differences':'No matches for this filter'}</h2><p>Interpret this within the reached states and captured evidence, never as a clean security verdict.</p>{filter!=='ALL'&&<Button variant="outline" onClick={()=>setFilter('ALL')}>Clear filter</Button>}</div>:visible.map(c=>{const key=c.candidate_evidence_id||c.baseline_evidence_id||c.identity;return <button key={key+c.kind} className={'change-row '+(selected===key?'selected':'')} onClick={()=>selectEvidence(key)} aria-pressed={selected===key}><span className="change-row-top"><Status value={c.kind}/><span>{c.category} · {c.state}</span></span><strong>{c.url_display||'Resource identity unavailable'}</strong><span>{c.reason.replaceAll('_',' ').toLowerCase()}</span>{c.new_origin&&<span className="origin-note">New observed origin · ownership unknown</span>}</button>;})}</section>
 <div className="evidence-column">{id&&<div className="panel-actions"><Button variant="ghost" onClick={()=>navigate('/evidence/'+id)}>Open evidence record <ArrowUpRight size={14}/></Button></div>}{selection?.category==='COOKIE'?<Notice title="Cookie attributes differ"><p>Values are never retained. Review the candidate journey and recorded profile for context.</p><Button variant="outline" onClick={()=>navigate('/runs/'+candidate+'/journey')}>Review candidate journey</Button></Notice>:<EvidencePanel id={id}/>}</div></div>
 <details className="all-findings"><summary>All scoped observations and standards context</summary><FindingList findings={result.data.findings}/></details></>)}</ResourceState>}
 </>;
}
