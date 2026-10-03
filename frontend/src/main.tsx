import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {LayoutDashboard,GitCompareArrows,Route,Fingerprint,LockKeyhole} from 'lucide-react';
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
 const destinations=useRef<Record<string,string>>({});
 useEffect(()=>{
  let live=true;
  window.cemBootstrap.then(s=>{if(live){setBearer(s.bearer);setDemo(s.demo);setSession('ready');}}).catch(e=>{if(live){setMessage(e.message);setSession('expired');}});
  const expired=()=>{setBearer(null);setMessage('The local session expired. Restart the local workbench to obtain a fresh bootstrap.');setSession('expired');};
  const pop=()=>setLocation(window.location.pathname+window.location.search);
  window.addEventListener('cem-session-expired',expired);window.addEventListener('popstate',pop);
  return ()=>{live=false;window.removeEventListener('cem-session-expired',expired);window.removeEventListener('popstate',pop);};
 },[]);
 function navigate(path:string){
  const previous=window.location.pathname;
  window.history.pushState(null,'',path);setLocation(path);
  if(previous!==path.split('?')[0]){window.scrollTo({top:0});setTimeout(()=>document.querySelector<HTMLElement>('h1')?.focus(),0);}
 }
 const [pathname,query='']=location.split('?'),parts=pathname.split('/').filter(Boolean);
 const screen=parts[0]==='runs'||parts[0]==='journey'?'Journey':parts[0]==='changes'?'Changes':parts[0]==='evidence'?'Evidence':'Assessments';
 destinations.current[screen]=location;
 const nav=[['Assessments','/assessments',LayoutDashboard],['Journey','/journey',Route],['Changes','/changes',GitCompareArrows],['Evidence','/evidence',Fingerprint]] as const;
 return <div className="app-shell"><a className="skip-link" href="#main">Skip to evidence workspace</a>
 <aside className="sidebar"><a className="brand" aria-label="Checkout Evidence Monitor home" href="/assessments" onClick={e=>{e.preventDefault();navigate('/assessments');}}><img src="/brand/mark.svg" width="48" height="48" alt=""/></a>
 <nav aria-label="Primary">{nav.map(([name,path,Icon])=><a key={name} href={destinations.current[name]||path} aria-current={screen===name?'page':undefined} onClick={e=>{e.preventDefault();navigate(destinations.current[name]||path);}}><Icon size={20} strokeWidth={1.6}/><span>{name}</span></a>)}</nav>
 <div className="sidebar-foot"><LockKeyhole size={16}/><span>LOCAL / V1.1</span></div></aside>
 <div className="workspace"><div className="session-strip"><div className="wordmark">checkout <small>/ Evidence Monitor</small></div><div className="session-state"><strong>{demo?'SYNTHETIC DEMO · READ ONLY':'LOCAL EVIDENCE WORKSPACE'}</strong><span><LockKeyhole size={16}/>Local session</span></div></div>
 <main id="main">{session==='loading'?<p role="status" className="state-message">Opening protected local session…</p>:session==='expired'?<Notice tone="danger" title="Local session required"><p>{message}</p><p>Use the link printed by the local CLI. Keep its one-time secret private.</p></Notice>:<React.Fragment key={screen+session}>{screen==='Assessments'?<Assessments search={query} navigate={navigate}/>:screen==='Changes'?<Changes search={query} navigate={navigate}/>:screen==='Journey'?<Journey key={parts[1]||'select'} id={parts[0]==='runs'?parts[1]||'':''} navigate={navigate}/>:<Evidence id={parts[1]||''} search={query} navigate={navigate}/>}</React.Fragment>}</main>
 <footer className="workspace-footer"><span>See the change. Follow the evidence.</span><span>Observations do not establish compliance or maliciousness.</span></footer></div></div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
