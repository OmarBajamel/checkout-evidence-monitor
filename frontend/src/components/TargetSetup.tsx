import {useState} from 'react';
import {ArrowLeft,ArrowRight,Check,Plus,Trash2} from 'lucide-react';
import {request} from '../api/client';
import type {PilotConfig,PilotStep} from '../api/operations';
import {Button} from './ui/button';
import {Notice} from './common';

export default function TargetSetup({initial,onSaved,onCancel,onBusyChange}:{initial?:PilotConfig;onSaved:()=>void;onCancel:()=>void;onBusyChange:(value:boolean)=>void}){
 const [stage,setStage]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [label,setLabel]=useState(initial?.label||''),[target,setTarget]=useState(initial?.target_id||''),[origin,setOrigin]=useState(initial?.origin||'');
 const [origins,setOrigins]=useState(initial?.grant.origins.filter(x=>x!==initial.origin).join('\n')||'');
 const [owner,setOwner]=useState(initial?.grant.owner||''),[hours,setHours]=useState(2),[cadence,setCadence]=useState(initial?.cadence_minutes||60);
 const [confirmed,setConfirmed]=useState(false),[steps,setSteps]=useState<PilotStep[]>(initial?.steps||[{id:'catalog',action:'goto',path:'/',selector:null,expected_state:'catalog'}]);
 function normalizedOrigin(value:string){const u=new URL(value.trim());if(u.protocol!=='https:'||u.username||u.password||u.port||u.search||u.hash||!['','/'].includes(u.pathname))throw new Error('Use an HTTPS origin without a path, credentials, or custom port.');return u.origin;}
 function configuration():PilotConfig{
  const primary=normalizedOrigin(origin),additional=origins.split('\n').map(x=>x.trim()).filter(Boolean).map(normalizedOrigin);
  return {target_id:target,label,origin:primary,cadence_minutes:cadence,consent:'UNSET',steps,
   ...(initial?.budgets?{budgets:initial.budgets}:{}),
   grant:{owner,assessor:owner,origins:[...new Set([primary,...additional])],issued_at:new Date().toISOString(),expires_at:new Date(Date.now()+hours*3600000).toISOString(),purpose:'AUTHORIZED_PUBLIC_STORE_OBSERVATION',authority_confirmed:true,no_payment_or_account_actions:true}};
 }
 function next(){
  setError('');
  try{
   if(stage===0){normalizedOrigin(origin);if(!label.trim()||!/^[a-z0-9-]{1,64}$/.test(target)||!owner.trim())throw new Error('Give the store a name, a lowercase target ID and an authorizing operator.');}
   if(stage===1){if(steps[0].action!=='goto')throw new Error('Start the journey with a page visit.');for(const s of steps){if(s.action==='goto'&&!/^\/[A-Za-z0-9/_-]{0,159}$/.test(s.path||''))throw new Error('Use a path without a query, identifiers or account/payment actions.');if(['goto','wait','assert'].includes(s.action)&&!s.selector?.trim())throw new Error('A visible-element check needs a CSS selector.');}}
   if(stage===2)configuration();
   setStage(x=>Math.min(3,x+1));
  }catch(e){setError((e as Error).message);}
 }
 function update(index:number,values:Partial<PilotStep>){setSteps(all=>all.map((s,i)=>i===index?{...s,...values}:s));}
 async function save(){setBusy(true);onBusyChange(true);setError('');try{await request('/api/v1/targets',undefined,configuration());onSaved();}catch(e){setError((e as Error).message);}finally{setBusy(false);onBusyChange(false);}}
 return <div className="setup-flow">
 <ol className="setup-progress" aria-label="Setup progress">{['Store','Journey','Authorization','Review'].map((name,i)=><li key={name} aria-current={stage===i?'step':undefined}><span>{i<stage?<Check size={14}/>:i+1}</span>{name}</li>)}</ol>
 {stage===0&&<><h3>Give your monitoring a clear scope.</h3><p className="muted">A fresh guest browser visits only the public pages and resource origins you declare. Saving starts no collection.</p><div className="form-grid">
 <label className="field"><span>Store name</span><input autoFocus value={label} maxLength={80} onChange={e=>{setLabel(e.target.value);if(!initial)setTarget(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,64));}} placeholder="My storefront"/></label>
 <label className="field"><span>Target ID</span><input value={target} disabled={!!initial} pattern="[a-z0-9-]{1,64}" maxLength={64} onChange={e=>setTarget(e.target.value)} placeholder="my-storefront"/></label>
 <label className="field full"><span>Store origin</span><input type="url" value={origin} onChange={e=>setOrigin(e.target.value)} maxLength={260} placeholder="https://your-store.example"/></label>
 <label className="field full"><span>Authorizing operator</span><input value={owner} onChange={e=>setOwner(e.target.value)} maxLength={120} placeholder="Your name or local operator reference"/></label></div></>}
 {stage===1&&<><h3>Define the visit, one state at a time.</h3><p className="muted">Visit public pages and confirm a visible element. No form input, sign-in, order or payment actions. State labels describe your intended observation; a selector can verify visible content.</p>
 <div className="step-editor">{steps.map((step,i)=><fieldset key={i}><legend>Step {i+1}</legend><div className="form-grid">
 <label className="field"><span>Action</span><select value={step.action} onChange={e=>update(i,{action:e.target.value as PilotStep['action'],path:e.target.value==='goto'?'/':null,selector:null,expected_state:e.target.value==='stop'?'stopped':'catalog'})}><option value="goto">Visit page</option><option value="wait">Wait for visible element</option><option value="assert">Check visible element</option><option value="stop">Stop observation</option></select></label>
 <label className="field"><span>Observation state</span><select value={step.expected_state} onChange={e=>update(i,{expected_state:e.target.value as PilotStep['expected_state']})}><option value="catalog">Catalog</option><option value="cart">Cart</option><option value="checkout">Checkout entry</option><option value="stopped">Stopped</option></select></label>
 {step.action==='goto'&&<label className="field"><span>Exact public path</span><input maxLength={160} value={step.path||''} onChange={e=>update(i,{path:e.target.value})} placeholder="/checkout"/></label>}
 {step.action!=='stop'&&<label className="field"><span>Visible CSS selector · required to confirm this state</span><input maxLength={160} value={step.selector||''} onChange={e=>update(i,{selector:e.target.value||null})} placeholder="main"/></label>}
 </div><Button variant="ghost" disabled={steps.length===1} onClick={()=>setSteps(all=>all.filter((_,n)=>n!==i))}><Trash2 size={15}/>Remove step {i+1}</Button></fieldset>)}</div>
 <Button variant="outline" disabled={steps.length>=12||steps.at(-1)?.action==='stop'} onClick={()=>setSteps(all=>[...all,{id:'step-'+crypto.randomUUID().slice(0,8),action:'goto',path:'/',expected_state:'checkout'}])}><Plus size={16}/>Add observation step</Button></>}
 {stage===2&&<><h3>Make the authorization explicit.</h3><p className="muted">This local record documents your authority and permitted resources. It is not permission from a third party. A grant lasts at most eight hours.</p><div className="form-grid">
 <label className="field full"><span>Additional approved resource origins · one per line</span><textarea value={origins} onChange={e=>setOrigins(e.target.value)} maxLength={1800} placeholder="https://your-approved-cdn.example"/><small>Up to seven additional HTTPS origins. An unlisted script or frame is blocked and the visit may be partial.</small></label>
 <label className="field"><span>Grant duration</span><select value={hours} onChange={e=>setHours(Number(e.target.value))}>{[1,2,4,8].map(h=><option key={h} value={h}>{h} hour{h>1?'s':''}</option>)}</select></label>
 <label className="field"><span>Monitoring cadence</span><select value={cadence} onChange={e=>setCadence(Number(e.target.value))}>{[15,30,60,120,240,1440].map(m=><option key={m} value={m}>{m<60?m+' minutes':m/60+' hours'}</option>)}</select></label></div>
 <Notice title="The local runner must remain active" tone="info"><p>Missed windows are disclosed. The runner will not fabricate or replay the visits it missed. Collection pauses when the grant expires.</p></Notice></>}
 {stage===3&&<><h3>Review your pilot setup.</h3><dl className="metadata-grid"><div><dt>Store</dt><dd>{label} · {target}</dd></div><div><dt>Primary origin</dt><dd>{origin}</dd></div><div><dt>Journey</dt><dd>{steps.length} steps · fresh public guest</dd></div><div><dt>Cadence / authorization</dt><dd>Every {cadence} minutes · {hours} hour grant</dd></div></dl><ol className="scope-list">{steps.map(s=><li key={s.id}>{s.action} · {s.path||s.selector||'end'} · {s.expected_state}</li>)}</ol><p className="muted">Additional origins: {origins.trim()||'None'}. Only GET/HEAD requests are permitted. Cookie consent remains unset; no consent banner is clicked automatically.</p>
 <label className="checkbox-field"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>I am authorized to observe these origins and pages. This scope excludes accounts, payments, order submission and other state-changing actions.</span></label>
 <Notice title="Saved paused" tone="info"><p>Review the saved target, prepare the authorized runner, then explicitly choose Run once or Start cadence. Saving does not visit the store.</p></Notice></>}
 {error&&<p role="alert" className="error-text">{error}</p>}
 <div className="dialog-actions"><Button variant="ghost" disabled={busy} onClick={onCancel}>Cancel</Button>{stage>0&&<Button variant="outline" disabled={busy} onClick={()=>{setStage(x=>x-1);setError('');}}><ArrowLeft size={16}/>Back</Button>}{stage<3?<Button onClick={next}>Continue<ArrowRight size={16}/></Button>:<Button disabled={!confirmed||busy} onClick={save}>{busy?'Saving…':'Save paused target'}</Button>}</div>
 </div>;
}
