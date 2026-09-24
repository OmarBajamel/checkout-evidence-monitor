import {useEffect,useState} from 'react';
declare global {interface Window {cemBootstrap:Promise<{bearer:string;demo:boolean}>}}
let bearer:string|null=null;
export class ApiError extends Error {constructor(public code:string,message:string){super(message);}}
export function setBearer(token:string|null){bearer=token;}
export async function request<T>(path:string,signal?:AbortSignal,body?:unknown):Promise<T>{
  if(!bearer)throw new ApiError('AUTH_REQUIRED','Open a fresh local bootstrap link.');
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+bearer,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),signal,cache:'no-store',credentials:'omit'});
  if(!response.ok){
    const e=await response.json().catch(()=>({error:{code:'INTERNAL_ERROR',message:'The local request failed.'}}));
    if(response.status===401){bearer=null;window.dispatchEvent(new Event('cem-session-expired'));}
    throw new ApiError(e.error?.code||'INTERNAL_ERROR',e.error?.message||'The local request failed.');
  }
  return response.json() as Promise<T>;
}
export function useResource<T>(path:string|null){
  const [data,setData]=useState<T|null>(null),[error,setError]=useState<Error|null>(null),[loading,setLoading]=useState(false),[revision,setRevision]=useState(0);
  useEffect(()=>{
    setData(null);setError(null);
    if(!path){setLoading(false);return;}
    const controller=new AbortController();setLoading(true);
    request<T>(path,controller.signal).then(setData).catch(e=>{if(e.name!=='AbortError')setError(e);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[path,revision]);
  return {data,error,loading,retry:()=>setRevision(x=>x+1)};
}
export async function exportRun(id:string,format:string){
  if(!bearer)throw new ApiError('AUTH_REQUIRED','Local session expired.');
  const response=await fetch('/api/v1/runs/'+encodeURIComponent(id)+'/export?format='+format,{headers:{Authorization:'Bearer '+bearer},cache:'no-store',credentials:'omit'});
  if(!response.ok){if(response.status===401){bearer=null;window.dispatchEvent(new Event('cem-session-expired'));}const e=await response.json();throw new ApiError(e.error?.code||'EXPORT_FAILED',e.error?.message||'Export failed.');}
  const blob=await response.blob();
  if(blob.size>52428800)throw new ApiError('ARTIFACT_LIMIT','Export exceeds its bound.');
  const url=URL.createObjectURL(blob),anchor=document.createElement('a');
  anchor.href=url;anchor.download='cem-'+id+'.'+format;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
