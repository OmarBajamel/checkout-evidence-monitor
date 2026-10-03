export type PilotStep = {id:string; action:'goto'|'wait'|'assert'|'stop'; path?:string|null; selector?:string|null; expected_state:'catalog'|'cart'|'checkout'|'stopped'; value?:null};
export interface PilotConfig {
 target_id:string; label:string; origin:string; cadence_minutes:number; consent:'UNSET'; steps:PilotStep[];
 grant:{owner:string;assessor:string;origins:string[];issued_at:string;expires_at:string;purpose:'AUTHORIZED_PUBLIC_STORE_OBSERVATION';authority_confirmed:true;no_payment_or_account_actions:true};
 budgets?:Record<string,number>;
}
export interface MonitorJob {id:string;target_id:string;status:string;queued_at:number;started_at:number|null;ended_at:number|null;run_id:string;code:string|null;cancel?:number}
export interface Target {id:string;label:string;origin:string;state:string;version:number;next_at:number|null;cadence_minutes:number;grant_expires_at:string;steps:number;baseline_id:string|null;last_job:MonitorJob|null}
export interface InboxItem {id:string;target_id:string;kind:string;message:string;baseline_id:string|null;candidate_id:string|null;created_at:number;last_at:number;repeats:number;read_at:number|null}
export interface OperationsData {targets:Target[];jobs:MonitorJob[];notices:InboxItem[];unread:number;worker:{status:string;heartbeat?:number|null;code?:string|null};demo:boolean}
export interface Review {id:string;baseline_id:string;candidate_id:string;decision:string;reason:string;at:number}
export interface Reviews {items:Review[];total:number;demo:boolean;notice?:string}
export function dateTime(value:number|string|null|undefined){if(value===null||value===undefined)return 'Not scheduled';return new Date(typeof value==='number'?value*1000:value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});}
