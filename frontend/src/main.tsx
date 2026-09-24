import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Files,GitCompareArrows,Route,ScanSearch,LockKeyhole} from 'lucide-react';
import {setBearer} from './api/client';
import {Notice} from './components/common';
import Assessments from './screens/Assessments';
import Changes from './screens/Changes';
import Journey from './screens/Journey';
import Evidence from './screens/Evidence';
import './styles/tokens.css';

function App(){
 const [session,setSession]=useState<'loading'|'ready'|'expired'>('loading'),[message,setMessage]=useState(''),[demo,setDemo]=useState(false);
 const [location,setLocation]=useState(window.location.pathname+window.location.search);
 useEffect(()=>{
  let live=true;
  window.cemBootstrap.then(s=>{if(live){setBearer(s.bearer);setDemo(s.demo);setSession('ready');}}).catch(e=>{if(live){setMessage(e.message);setSession('expired');}});
  const expired=()=>{setBearer(null);setMessage('The local session expired. Restart the local workbench to obtain a fresh bootstrap.');setSession('expired');};
  const pop=()=>setLocation(window.location.pathname+window.location.search);
  window.addEventListener('cem-session-expired',expired);window.addEventListener('popstate',pop);
  return ()=>{live=false;window.removeEventListener('cem-session-expired',expired);window.removeEventListener('popstate',pop);};
 },[]);
 function navigate(path:string){window.history.pushState(null,'',path);setLocation(path);window.scrollTo({top:0});setTimeout(()=>document.querySelector<HTMLElement>('h1')?.focus(),0);}
 const [pathname,query='']=location.split('?'),parts=pathname.split('/').filter(Boolean);
 const screen=parts[0]==='runs'||parts[0]==='journey'?'Journey':parts[0]==='changes'?'Changes':parts[0]==='evidence'?'Evidence':'Assessments';
 const nav=[['Assessments','/assessments',Files],['Journey','/journey',Route],['Changes','/changes',GitCompareArrows],['Evidence','/evidence',ScanSearch]] as const;
 return <div className="app-shell"><a className="skip-link" href="#main">Skip to evidence workspace</a><aside className="sidebar"><a className="brand" href="/assessments" onClick={e=>{e.preventDefault();navigate('/assessments');}}><svg viewBox="0 0 40 40" aria-hidden><path d="M4 28H13V18H23V9H36V34H23" fill="none" stroke="currentColor" strokeWidth="3"/><rect x="20" y="25" width="6" height="6" fill="currentColor"/></svg><span>Checkout{' '}<br/>Evidence Monitor</span></a><div className="nav-label">LOCAL WORKBENCH</div><nav aria-label="Primary">{nav.map(([name,path,Icon],i)=><a key={name} href={path} aria-current={screen===name?'page':undefined} onClick={e=>{e.preventDefault();navigate(path);}}><Icon size={18}/><span>{name}</span><small>0{i+1}</small></a>)}</nav><div className="sidebar-foot"><LockKeyhole size={15}/><span>Local evidence.<br/>Bounded conclusions.</span></div></aside><div className="workspace"><div className="session-strip"><span><i aria-hidden/> Local session · loopback only</span><strong>{demo?'SYNTHETIC DEMO · READ ONLY':'RECORDED EVIDENCE'}</strong></div><main id="main">
 {session==='loading'?<p role="status" className="state-message">Opening protected local session…</p>:session==='expired'?<Notice tone="danger" title="Local session required"><p>{message}</p><p>No evidence is loaded. Use the link printed by the local CLI; do not send its secret to anyone.</p></Notice>:<React.Fragment key={screen+session}>{screen==='Assessments'?<Assessments navigate={navigate}/>:screen==='Changes'?<Changes search={query} navigate={navigate}/>:screen==='Journey'?<Journey key={parts[1]||'select'} id={parts[0]==='runs'?parts[1]||'':''} navigate={navigate}/>:<Evidence id={parts[1]||''} search={query} navigate={navigate}/>}</React.Fragment>}
 </main><footer className="workspace-footer"><span>See the change. Follow the evidence.</span><span>Observations do not establish compliance or maliciousness.</span></footer></div></div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
