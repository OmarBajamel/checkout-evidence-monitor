import type {Meta,StoryObj} from '@storybook/react-vite';
import {Notice,ResourceState,Status,Dialog} from './common';
import {Button} from './ui/button';
import {useState} from 'react';

const meta={title:'Workbench/Recorded states',component:Notice,args:{title:'Story fixture',children:'Authored synthetic state'},parameters:{layout:'padded'}} satisfies Meta<typeof Notice>;
export default meta;
type Story=StoryObj<typeof meta>;
export const Empty:Story={args:{title:'No recorded evidence yet',children:'Import a sanitized record explicitly. Opening this screen starts no collection.'}};
export const Partial:Story={args:{title:'Checkout evidence is incomplete',children:<><Status value="PARTIAL"/><p>The declared checkout state was not reached. Missing scripts remain unobservable.</p></>}};
export const Incompatible:Story={args:{title:'These visits are not comparable',children:'Consent differs: DECLINED / ACCEPTED. No script diff is inferred.'}};
export const BodyUnavailable:Story={args:{title:'Body evidence unavailable',children:<><code>BODY_OVERSIZED</code><p>The request remains in the inventory. No hash is fabricated.</p></>}};
export const LongText:Story={args:{title:'Sanitized resource identity',children:<code>{'https://shop.cem.test:8765/scripts/checkout.js?'+('[redacted-identity]'.repeat(20))}</code>}};
export const Loading:Story={render:()=> <ResourceState loading error={null} retry={()=>{}}><span/></ResourceState>};
export const ErrorState:Story={render:()=> <ResourceState loading={false} error={new Error('The protected local session expired. Obtain a fresh terminal bootstrap link.')} retry={()=>{}}><span/></ResourceState>};
export const BaselineDialog:Story={render:function Baseline(){const [open,setOpen]=useState(false);return <><Button onClick={()=>setOpen(true)}>Select baseline</Button><Dialog title="Choose this baseline" open={open} onClose={()=>setOpen(false)}><p>Story fixture only. Selection does not establish safety.</p><label className="field">Reason<textarea/></label><div className="dialog-actions"><Button onClick={()=>setOpen(false)}>Cancel</Button></div></Dialog></>;}};
