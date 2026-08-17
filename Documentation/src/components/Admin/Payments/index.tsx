"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle, Banknote, BarChart3, ChevronLeft, ChevronRight,
  CircleDollarSign, CreditCard, FileClock, Globe2, Landmark,
  RefreshCw, RotateCcw, Search, ShieldAlert, SlidersHorizontal,
  WalletCards,
} from "lucide-react";
import {
  type AdminCurrency, type AdminFxRate, type AdminPayment,
  type AdminPaymentDashboard, type AdminPaymentMethod,
  getAdminPaymentDashboard, listAdminCountries, listAdminCurrencies,
  listAdminFailedPayments, listAdminFeesCommissions, listAdminFxRates,
  listAdminPaymentDisputes, listAdminPaymentMethods, listAdminPaymentProviders,
  listAdminPayments, listAdminPayouts, listAdminReconciliation,
  listAdminRefunds, listAdminRiskEvents, refundAdminPayment,
} from "@/lib/api/endpoints/admin";

export type PaymentView =
  | "dashboard" | "transactions" | "methods" | "providers" | "refunds"
  | "disputes" | "payouts" | "pending-payouts" | "failed" | "risk"
  | "reconciliation" | "currencies" | "countries" | "fees"
  | "reports" | "audit";

type GenericRow = Record<string, any>;

const titles: Record<PaymentView, [string,string,string]> = {
  dashboard:["Payment command center","Payments Dashboard","Monitor collections, refunds, seller settlement, commissions and payment exceptions."],
  transactions:["Payment operations","Transactions","Trace every payment against its order, customer, provider and final status."],
  methods:["Payment configuration","Payment Methods","Compare payment methods and their transaction performance."],
  providers:["Payment infrastructure","Payment Providers","See the gateways/providers configured for Xerin, their supported methods, currencies and status."],
  refunds:["Payment exceptions","Refunds","Review refunded and refundable payments with full audit context."],
  disputes:["Payment exceptions","Disputes & Chargebacks","Track disputed transactions from opening through investigation and resolution."],
  payouts:["Seller settlement","Seller Payouts","Monitor seller payout requests and completed settlement transfers."],
  "pending-payouts":["Seller settlement","Pending Payouts","Focus on payouts awaiting approval or provider processing."],
  failed:["Payment exceptions","Failed Payments","Investigate failed attempts and provider failure reasons."],
  risk:["Risk & compliance","Fraud & Risk","Review suspicious activity and payment risk events requiring attention."],
  reconciliation:["Financial control","Reconciliation","Compare Xerin records against provider amounts and references."],
  currencies:["Currency management","Currencies & FX","Manage supported currencies and exchange rates for TZS and USD display."],
  countries:["Market configuration","Countries","Control countries, currencies, collections and payouts enabled by the platform."],
  fees:["Marketplace economics","Fees & Commissions","Review gateway fees, marketplace commissions and seller deductions."],
  reports:["Financial intelligence","Payment Reports","Reporting workspace for collections, refunds, payouts and provider performance."],
  audit:["Financial governance","Payment Audit Logs","Trace administrative payment actions and lifecycle events."],
};

const money=(n:number,c="TZS")=>new Intl.NumberFormat("en-TZ",{style:"currency",currency:c,maximumFractionDigits:c==="TZS"?0:2}).format(n);
const pretty=(v?:string|null)=>(v||"unknown").replaceAll("_"," ").replace(/\b\w/g,l=>l.toUpperCase());

export default function AdminPayments({view}:{view:PaymentView}) {
  const [rows,setRows]=useState<GenericRow[]>([]);
  const [methods,setMethods]=useState<AdminPaymentMethod[]>([]);
  const [dashboard,setDashboard]=useState<AdminPaymentDashboard|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [backendPending,setBackendPending]=useState(false);
  const [query,setQuery]=useState("");
  const [debounced,setDebounced]=useState("");
  const [status,setStatus]=useState("all");
  const [page,setPage]=useState(1);
  const [pageSize,setPageSize]=useState(20);
  const [total,setTotal]=useState(0);
  const [totalPages,setTotalPages]=useState(0);
  const [selected,setSelected]=useState<AdminPayment|null>(null);
  const [refundReason,setRefundReason]=useState("");
  const [refunding,setRefunding]=useState(false);
  const [eyebrow,title,description]=titles[view];

  useEffect(()=>{
    const id=window.setTimeout(()=>{setDebounced(query.trim());setPage(1)},350);
    return()=>window.clearTimeout(id);
  },[query]);

  const load=async()=>{
    setLoading(true); setError(""); setBackendPending(false);
    const params={page,page_size:pageSize,search:debounced||undefined,status_filter:status==="all"?undefined:status};
    try{
      if(view==="dashboard"){setDashboard(await getAdminPaymentDashboard());setRows([]);}
      else if(view==="methods"){setMethods(await listAdminPaymentMethods());setRows([]);}
      else if(view==="transactions"||view==="refunds"||view==="failed"){
        const result=view==="refunds"?await listAdminRefunds(params):view==="failed"?await listAdminFailedPayments(params):await listAdminPayments(params);
        setRows(result.results);setTotal(result.total);setTotalPages(result.total_pages??Math.ceil(result.total/result.page_size));
      }else if(view==="providers"){const r=await listAdminPaymentProviders(params);setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="payouts"||view==="pending-payouts"){const r=await listAdminPayouts({...params,status_filter:view==="pending-payouts"?"pending":params.status_filter});setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="disputes"){const r=await listAdminPaymentDisputes(params);setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="risk"){const r=await listAdminRiskEvents(params);setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="reconciliation"){const r=await listAdminReconciliation(params);setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="countries"){const r=await listAdminCountries(params);setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="fees"){const r=await listAdminFeesCommissions(params);setRows(r.results);setTotal(r.total);setTotalPages(r.total_pages??Math.ceil(r.total/pageSize));}
      else if(view==="currencies"){
        const [c,fx]=await Promise.all([listAdminCurrencies({page:1,page_size:100,search:debounced||undefined}),listAdminFxRates({page:1,page_size:100,search:debounced||undefined})]);
        setRows([...c.results,...fx.results]);setTotal(c.total+fx.total);setTotalPages(1);
      }else{setBackendPending(true);setRows([]);setTotal(0);setTotalPages(0);}
    }catch(e){
      if(["providers","payouts","pending-payouts","disputes","risk","reconciliation","currencies","countries","fees","dashboard","reports","audit"].includes(view)){
        setBackendPending(true);setRows([]);setTotal(0);setTotalPages(0);
      }else setError(e instanceof Error?e.message:"Unable to load payment data");
    }finally{setLoading(false)}
  };

  useEffect(()=>{void load()},[view,page,pageSize,debounced,status]);

  const doRefund=async()=>{
    if(!selected||refundReason.trim().length<5)return;
    setRefunding(true);
    try{await refundAdminPayment(selected.id,refundReason.trim());setSelected(null);setRefundReason("");await load()}
    catch(e){setError(e instanceof Error?e.message:"Refund failed")}
    finally{setRefunding(false)}
  };

  return <div className="space-y-5">
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">{eyebrow}</p><h2 className="mt-1 text-2xl font-bold text-slate-900">{title}</h2><p className="mt-1 max-w-4xl text-sm leading-6 text-slate-500">{description}</p></div>
        <button onClick={()=>void load()} className="inline-flex h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-600"><RefreshCw size={15}/>Refresh</button>
      </div>
    </section>

    {view==="dashboard"?<DashboardView data={dashboard} loading={loading} pending={backendPending}/>
    :view==="methods"?<MethodsView methods={methods} loading={loading}/>
    :<>
      {view==="currencies"&&<section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]"><Globe2 size={18}/></span><div><h3 className="font-bold text-slate-900">TZS ↔ USD architecture</h3><p className="mt-1 text-sm leading-6 text-slate-500">No exchange rate is hardcoded in the frontend. TZS/USD currencies and conversion rates are expected from backend currency and FX tables so the same rate can later be reused by product display, checkout, reports and seller settlement.</p></div></div></section>}
      {error&&<div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {backendPending?<PendingNotice title={title}/>:<section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-5 md:flex-row">
          <div className="relative flex-1"><Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={`Search ${title.toLowerCase()}...`} className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm outline-none focus:border-orange-300"/></div>
          {view!=="currencies"&&<select value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}} className="h-11 rounded-xl border border-slate-200 bg-white px-4 text-sm"><option value="all">All statuses</option>{["pending","processing","completed","active","inactive","failed","refunded","resolved","closed"].map(v=><option key={v} value={v}>{pretty(v)}</option>)}</select>}
        </div>
        <DataTable view={view} rows={rows} loading={loading} onReview={setSelected}/>
        {!loading&&total>0&&view!=="currencies"&&<Pagination page={page} pageSize={pageSize} total={total} totalPages={totalPages} onPage={setPage} onPageSize={s=>{setPageSize(s);setPage(1)}}/>}
      </section>}
    </>}

    {selected&&<div className="fixed inset-0 z-[100] flex justify-end bg-black/45" onMouseDown={()=>setSelected(null)}><aside onMouseDown={e=>e.stopPropagation()} className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl"><div className="flex justify-between"><div><p className="text-xs font-bold uppercase text-[#f47524]">Payment review</p><h3 className="mt-1 text-xl font-bold">{selected.reference||selected.id}</h3></div><button onClick={()=>setSelected(null)} className="text-2xl text-slate-400">×</button></div><dl className="mt-6 grid grid-cols-2 gap-3 text-sm">{[["Customer",selected.customer_name],["Order",selected.order_number],["Method",pretty(selected.method)],["Provider",selected.provider||"Direct"],["Amount",money(selected.amount,selected.currency)],["Status",pretty(selected.status)]].map(([k,v])=><div key={k} className="rounded-xl bg-slate-50 p-3"><dt className="text-slate-500">{k}</dt><dd className="mt-1 font-semibold">{v}</dd></div>)}</dl>{selected.status==="completed"&&<div className="mt-6 border-t pt-5"><h4 className="font-bold">Issue full refund</h4><textarea value={refundReason} onChange={e=>setRefundReason(e.target.value)} placeholder="Reason for refund" className="mt-3 min-h-24 w-full rounded-xl border p-3 text-sm"/><button disabled={refunding||refundReason.trim().length<5} onClick={()=>void doRefund()} className="mt-3 w-full rounded-xl bg-red-600 py-3 text-sm font-semibold text-white disabled:opacity-40">{refunding?"Processing...":`Refund ${money(selected.amount,selected.currency)}`}</button></div>}</aside></div>}
  </div>;
}

function DashboardView({data,loading,pending}:{data:AdminPaymentDashboard|null;loading:boolean;pending:boolean}) {
  if(loading)return <Loading text="Loading payment dashboard..."/>;
  if(pending||!data)return <PendingNotice title="Payments Dashboard"/>;
  const cards:[[string,string|number,any],...Array<[string,string|number,any]>]=[
    ["Processed volume",money(data.processed_volume,data.currency),CircleDollarSign],
    ["Successful payments",data.successful_payments,CreditCard],
    ["Pending payments",data.pending_payments,FileClock],
    ["Failed payments",data.failed_payments,AlertTriangle],
    ["Refunded amount",money(data.refunded_amount,data.currency),RotateCcw],
    ["Pending payouts",data.pending_payouts,WalletCards],
    ["Platform commission",money(data.platform_commission,data.currency),Landmark],
    ["Seller earnings",money(data.seller_earnings,data.currency),Banknote],
  ];
  return <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([l,v,I])=><Metric key={l} label={l} value={v} icon={I}/>)}</section>;
}

function MethodsView({methods,loading}:{methods:AdminPaymentMethod[];loading:boolean}) {
  if(loading)return <Loading text="Loading payment methods..."/>;
  if(!methods.length)return <Empty text="No payment method activity recorded yet."/>;
  return <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{methods.map(m=><article key={`${m.method}-${m.provider}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start justify-between"><div><p className="text-lg font-bold">{pretty(m.method)}</p><p className="text-sm text-slate-500">{m.provider}</p></div><span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700">{m.transactions} txns</span></div><p className="mt-5 text-2xl font-bold">{money(m.volume,m.currency)}</p><div className="mt-4 grid grid-cols-2 gap-3"><div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-slate-500">Successful</p><p className="font-bold text-emerald-700">{m.completed}</p></div><div className="rounded-xl bg-red-50 p-3"><p className="text-xs text-slate-500">Failed</p><p className="font-bold text-red-700">{m.failed}</p></div></div></article>)}</section>;
}

function DataTable({view,rows,loading,onReview}:{view:PaymentView;rows:GenericRow[];loading:boolean;onReview:(p:AdminPayment)=>void}) {
  if(loading)return <Loading text={`Loading ${titles[view][1].toLowerCase()}...`}/>;
  if(!rows.length)return <Empty text={`No ${titles[view][1].toLowerCase()} records found.`}/>;

  if(view==="currencies"){
    const currencies=rows.filter(r=>"is_base" in r) as AdminCurrency[];
    const fx=rows.filter(r=>"base_currency" in r) as AdminFxRate[];
    return <div className="p-5 space-y-6"><SimpleTable headers={["Currency","Symbol","Base","Status"]} rows={currencies.map(c=>[`${c.code} · ${c.name}`,c.symbol,c.is_base?"Base":"Quote",c.is_active?"Active":"Inactive"])}/><div><h3 className="font-bold">Exchange rate table</h3><p className="mt-1 text-xs text-slate-500">Rates come from backend configuration, not from hardcoded frontend values.</p><div className="mt-3"><SimpleTable headers={["Base","Quote","Rate","Source","Effective","Status"]} rows={fx.map(r=>[r.base_currency,r.quote_currency,String(r.rate),r.source||"Configured",new Date(r.effective_at).toLocaleString(),r.is_active?"Active":"Inactive"])}/></div></div></div>;
  }

  if(["transactions","refunds","failed"].includes(view)){
    return <div className="overflow-x-auto"><table className="w-full min-w-[950px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Reference / Order","Customer","Method / Provider","Amount","Status","Created","Action"].map(h=><th key={h} className="px-5 py-3">{h}</th>)}</tr></thead><tbody className="divide-y">{(rows as AdminPayment[]).map(p=><tr key={p.id}><td className="px-5 py-4"><p className="font-semibold">{p.reference||`PAY-${p.id.slice(0,8)}`}</p><p className="text-xs text-slate-500">Order {p.order_number}</p></td><td className="px-5 py-4">{p.customer_name}<p className="text-xs text-slate-500">{p.customer_email}</p></td><td className="px-5 py-4">{pretty(p.method)}<p className="text-xs text-slate-500">{p.provider||"Direct"}</p></td><td className="px-5 py-4 font-semibold">{money(p.amount,p.currency)}</td><td className="px-5 py-4"><Status value={p.status}/></td><td className="px-5 py-4 text-slate-500">{new Date(p.created_at).toLocaleString()}</td><td className="px-5 py-4"><button onClick={()=>onReview(p)} className="font-semibold text-[#f47524]">Review</button></td></tr>)}</tbody></table></div>;
  }

  const keysByView:Partial<Record<PaymentView,string[]>>={
    providers:["name","provider_type","supported_currencies","supported_methods","status"],
    payouts:["seller_name","amount","currency","provider","reference","status"],
    "pending-payouts":["seller_name","amount","currency","provider","reference","status"],
    disputes:["order_number","customer_name","seller_name","amount","currency","status"],
    risk:["event_type","user_name","score","severity","status"],
    reconciliation:["order_number","provider","expected_amount","provider_amount","difference","status"],
    countries:["name","code","currency_code","payments_enabled","payouts_enabled","is_active"],
    fees:["name","scope","rate_type","rate_value","provider","is_active"],
  };
  const keys=keysByView[view]||Object.keys(rows[0]).slice(0,6);
  return <SimpleTable headers={keys.map(pretty)} rows={rows.map(r=>keys.map(k=>Array.isArray(r[k])?r[k].join(", "):typeof r[k]==="boolean"?(r[k]?"Yes":"No"):String(r[k]??"—")))}/>;
}

function SimpleTable({headers,rows}:{headers:string[];rows:string[][]}) {
  return <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{headers.map(h=><th key={h} className="px-4 py-3">{h}</th>)}</tr></thead><tbody className="divide-y">{rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j} className="px-4 py-4 text-slate-700">{v}</td>)}</tr>)}</tbody></table></div>;
}

function PendingNotice({title}:{title:string}) {
  return <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><div className="flex gap-3"><SlidersHorizontal className="mt-0.5 text-amber-700" size={18}/><div><h3 className="font-bold text-amber-900">{title} frontend is ready</h3><p className="mt-1 text-sm leading-6 text-amber-800">The workspace and API contract are prepared, but this backend endpoint is not available yet. No payment provider, payout, currency or FX value is invented in the frontend. Once the finance backend task creates the real tables/endpoints, this page will display them.</p></div></div></section>;
}

function Pagination({page,pageSize,total,totalPages,onPage,onPageSize}:{page:number;pageSize:number;total:number;totalPages:number;onPage:(p:number)=>void;onPageSize:(s:number)=>void}) {
  const from=total?((page-1)*pageSize+1):0,to=Math.min(page*pageSize,total);
  return <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><p className="text-sm text-slate-500">Showing <b>{from}-{to}</b> of <b>{total}</b></p><div className="flex items-center gap-2"><select value={pageSize} onChange={e=>onPageSize(Number(e.target.value))} className="h-10 rounded-xl border px-3 text-sm">{[10,20,50,100].map(s=><option key={s} value={s}>{s} / page</option>)}</select><button disabled={page<=1} onClick={()=>onPage(page-1)} className="inline-flex h-10 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-40"><ChevronLeft size={14}/>Previous</button><span className="min-w-24 text-center text-xs text-slate-500">Page {page} of {Math.max(totalPages,1)}</span><button disabled={page>=totalPages||!totalPages} onClick={()=>onPage(page+1)} className="inline-flex h-10 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-40">Next<ChevronRight size={14}/></button></div></div>;
}
function Metric({icon:Icon,label,value}:{icon:any;label:string;value:string|number}) {return <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]"><Icon size={17}/></span><p className="mt-4 text-2xl font-bold">{value}</p><p className="mt-1 text-xs text-slate-500">{label}</p></article>}
function Status({value}:{value:string}) {return <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">{pretty(value)}</span>}
function Loading({text}:{text:string}) {return <div className="p-12 text-center text-sm text-slate-500"><RefreshCw className="mx-auto animate-spin" size={20}/><p className="mt-3">{text}</p></div>}
function Empty({text}:{text:string}) {return <div className="p-12 text-center"><CreditCard className="mx-auto text-slate-300" size={32}/><p className="mt-3 font-semibold text-slate-700">{text}</p></div>}
