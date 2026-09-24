import {useState} from 'react';
import {useResource} from '../api/client';
import type {Journey as JourneyData,RunPage} from '../api/types';
import {ExportControl,Notice,PageTitle,ProfileDetails,ResourceState,RunSelect,Status} from '../components/common';
import {Button} from '../components/ui/button';

export default function Journey({id,navigate}:{id:string;navigate:(path:string)=>void}){
 const runList=useResource<RunPage>(!id?'/api/v1/runs?limit=100':null);
 const r=useResource<JourneyData>(id?'/api/v1/runs/'+id+'/journey':null);
 const [step,setStep]=useState('');
 const selected=r.data?.steps.find(s=>s.id===step)||r.data?.steps[0];
 const evidence=r.data?.evidence.filter(e=>e.step_id===selected?.id)||[];
 return <><PageTitle eyebrow="02 / Reached states" title="Journey" description="See where the observer reached, stopped, or lacked visibility.">{id&&<ExportControl id={id}/>}</PageTitle>
 {!id?<ResourceState {...runList} empty={!!runList.data&&!runList.data.total}><RunSelect label="Recorded journey" value="" onChange={v=>navigate('/runs/'+v+'/journey')} runs={runList.data?.items||[]}/></ResourceState>:<ResourceState {...r}>{r.data&&<>
 <ProfileDetails profile={r.data.profile}/><div className="inline-meta"><Status value={r.data.provenance}/><span>Complete windows: {r.data.complete_states.join(', ')||'none'}</span></div>
 {r.data.limitation_codes.length>0&&<Notice title="This record has visibility limits"><p>{r.data.limitation_codes.join(' · ')}</p></Notice>}
 {!r.data.steps.length?<Notice title="No declared steps in this record"><p>Imported evidence may have incomplete journey context.</p></Notice>:<div className="journey-layout"><ol className="stage-list">{r.data.steps.map((s,i)=><li key={s.id}><button aria-pressed={selected?.id===s.id} className={selected?.id===s.id?'selected':''} onClick={()=>setStep(s.id)}><span className="stage-number">{String(i+1).padStart(2,'0')}</span><span><strong>{s.state}</strong><Status value={s.status}/></span></button></li>)}</ol><section className="step-detail"><div className="eyebrow">Selected state</div><h2>{selected?.state}</h2><p>{selected?.reason?.replaceAll('_',' ')||'The declared state was observed within the bounded window.'}</p>{selected?.status!=='REACHED'&&<Notice title="Dependent checks were not evaluated"><p>Missing coverage cannot establish that a script disappeared or that this state was safe.</p></Notice>}<h3>Linked evidence</h3>{evidence.length?<ul className="evidence-links">{evidence.map(e=><li key={e.id}><span className="eyebrow">{e.kind} · {e.frame_id}</span><strong>{e.url_display||'Inline metadata only'}</strong><Button variant="outline" onClick={()=>navigate('/evidence/'+e.id)}>View evidence</Button></li>)}</ul>:<p>No evidence linked to this step.</p>}</section></div>}
 <details><summary>Observed frames and visibility</summary><dl className="metadata-grid">{r.data.frames.map(f=><div key={f.id}><dt>{f.id} · {f.visibility}</dt><dd>{f.origin||'Origin unavailable'}</dd></div>)}</dl></details>
 </>}</ResourceState>}
 </>;
}
