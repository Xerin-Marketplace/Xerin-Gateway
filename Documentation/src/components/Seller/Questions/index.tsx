"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, HelpCircle, MessageCircleReply, RefreshCw, Search, X } from "lucide-react";
import toast from "react-hot-toast";
import { sellerFeedbackApi } from "@/lib/api/endpoints/seller-feedback";
import { getMyProducts } from "@/lib/api/endpoints/products";
import type { Product } from "@/types/api/product";
import type { SellerProductQuestion } from "@/types/api/seller-feedback";

const err=(e:unknown)=>{const x=e as {response?:{data?:{detail?:string}};message?:string};return x.response?.data?.detail||x.message||"Request failed.";};

export default function SellerQuestions() {
  const [rows,setRows]=useState<SellerProductQuestion[]>([]);
  const [products,setProducts]=useState<Product[]>([]);
  const [page,setPage]=useState(1);
  const [pageSize,setPageSize]=useState(20);
  const [total,setTotal]=useState(0);
  const [unansweredOnly,setUnansweredOnly]=useState(false);
  const [search,setSearch]=useState("");
  const [loading,setLoading]=useState(true);
  const [target,setTarget]=useState<SellerProductQuestion|null>(null);
  const [answer,setAnswer]=useState("");
  const [busy,setBusy]=useState(false);

  const load=async()=>{
    setLoading(true);
    try{
      const [data,myProducts]=await Promise.all([
        sellerFeedbackApi.questions({page,page_size:pageSize,unanswered_only:unansweredOnly}),
        getMyProducts().catch(()=>[]),
      ]);
      setRows(data.results); setTotal(data.total); setProducts(myProducts);
    }catch(e){toast.error(err(e));}finally{setLoading(false);}
  };
  useEffect(()=>{void load();},[page,pageSize,unansweredOnly]);

  const productMap=useMemo(()=>new Map(products.map(p=>[p.id,p.name])),[products]);
  const visible=useMemo(()=>{
    const q=search.trim().toLowerCase();
    if(!q)return rows;
    return rows.filter(r=>[r.question,productMap.get(r.product_id)||"",...r.answers.map(a=>a.answer)].join(" ").toLowerCase().includes(q));
  },[rows,search,productMap]);
  const totalPages=total?Math.ceil(total/pageSize):0;

  const submit=async()=>{
    if(!target||answer.trim().length<2)return;
    setBusy(true);
    try{
      await sellerFeedbackApi.answerQuestion(target.id,answer.trim());
      toast.success("Official seller answer published.");
      setTarget(null);setAnswer("");await load();
    }catch(e){toast.error(err(e));}finally{setBusy(false);}
  };

  return <div className="space-y-5">
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[.14em] text-[#f7941d]">Seller Phase 9</p><h1 className="mt-1 text-2xl font-bold dark:text-white">Product Questions & Answers</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500 dark:text-white/60">Answer customer questions about products in your own catalog. Seller answers are recorded by the backend as official answers.</p></div>
        <button onClick={()=>void load()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold dark:border-white/10"><RefreshCw size={15}/>Refresh</button>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3"><Metric label="Questions" value={String(total)}/><Metric label="Unanswered on page" value={String(rows.filter(x=>x.answer_count===0).length)}/><Metric label="Answered on page" value={String(rows.filter(x=>x.answer_count>0).length)}/></div>
    </section>

    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
      <div className="flex flex-col gap-3 border-b border-slate-100 p-5 lg:flex-row lg:items-center lg:justify-between dark:border-white/10">
        <div><h2 className="font-bold dark:text-white">Customer Questions</h2><p className="mt-1 text-xs text-slate-400">Unanswered filtering and pagination are server-side. Search applies to the current page.</p></div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="relative"><Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter current page..." className="h-11 min-w-[250px] rounded-xl border border-slate-200 pl-10 pr-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"/></label>
          <label className="flex h-11 cursor-pointer items-center gap-2 rounded-xl border border-slate-200 px-3 text-sm dark:border-white/10"><input type="checkbox" checked={unansweredOnly} onChange={e=>{setUnansweredOnly(e.target.checked);setPage(1);}}/><span>Unanswered only</span></label>
        </div>
      </div>

      {loading?<div className="p-14 text-center text-sm text-slate-500"><RefreshCw size={20} className="mx-auto animate-spin"/><p className="mt-2">Loading questions...</p></div>:
      <div className="divide-y divide-slate-100 dark:divide-white/10">
        {visible.map(row=><article key={row.id} className="p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-[11px]"><span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-600">{productMap.get(row.product_id)||`Product ${row.product_id.slice(0,8)}…`}</span><span className={row.answer_count?"rounded-full bg-emerald-50 px-2 py-1 font-bold text-emerald-700":"rounded-full bg-amber-50 px-2 py-1 font-bold text-amber-700"}>{row.answer_count?`${row.answer_count} answer${row.answer_count===1?"":"s"}`:"Needs answer"}</span><span className="text-slate-400">{new Date(row.created_at).toLocaleString()}</span></div>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-800 dark:text-white/80">{row.question}</p>
              {row.answers.length>0&&<div className="mt-4 space-y-2">{row.answers.map(a=><div key={a.id} className={a.is_seller_answer?"rounded-xl border border-orange-100 bg-orange-50/70 p-3":"rounded-xl border border-slate-200 bg-slate-50 p-3"}><div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">{a.is_seller_answer&&<span className="text-[#c66c0b]">Seller answer</span>}{a.is_official&&<span>Official</span>}<span>{a.helpful_count} helpful</span></div><p className="mt-1 text-sm leading-6 text-slate-700">{a.answer}</p></div>)}</div>}
            </div>
            <button onClick={()=>{setTarget(row);setAnswer("");}} className="inline-flex h-fit items-center justify-center gap-2 rounded-xl border border-orange-200 bg-orange-50 px-3 py-2 text-xs font-semibold text-[#c66c0b]"><MessageCircleReply size={14}/>{row.answer_count?"Add answer":"Answer"}</button>
          </div>
        </article>)}
        {!visible.length&&<div className="p-14 text-center"><HelpCircle size={28} className="mx-auto text-slate-300"/><p className="mt-3 font-semibold text-slate-600 dark:text-white/70">No questions found</p></div>}
      </div>}

      <Pagination page={page} pageSize={pageSize} total={total} totalPages={totalPages} onPage={setPage} onSize={x=>{setPageSize(x);setPage(1);}}/>
    </section>

    {target&&<div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/55 p-4"><div className="w-full max-w-xl rounded-2xl bg-white p-5 shadow-2xl dark:bg-[#1f2937]"><div className="flex items-center justify-between"><h2 className="text-lg font-bold dark:text-white">Answer Product Question</h2><button onClick={()=>!busy&&setTarget(null)} className="rounded-lg border p-2 dark:border-white/10"><X size={15}/></button></div><p className="mt-4 rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">{target.question}</p><textarea value={answer} onChange={e=>setAnswer(e.target.value)} maxLength={4000} className="mt-4 min-h-36 w-full rounded-xl border border-slate-200 p-3 text-sm outline-none focus:border-orange-300 dark:border-white/10 dark:bg-white/5 dark:text-white" placeholder="Write a clear answer for the customer..."/><button disabled={busy||answer.trim().length<2} onClick={()=>void submit()} className="mt-4 w-full rounded-xl bg-[#f7941d] py-3 text-sm font-semibold text-white disabled:opacity-50">{busy?"Publishing...":"Publish Official Answer"}</button></div></div>}
  </div>;
}

function Metric({label,value}:{label:string;value:string}){return <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/[.03]"><p className="text-xl font-bold dark:text-white">{value}</p><p className="mt-1 text-xs text-slate-500">{label}</p></div>}
function Pagination({page,pageSize,total,totalPages,onPage,onSize}:{page:number;pageSize:number;total:number;totalPages:number;onPage:(x:number)=>void;onSize:(x:number)=>void}){const from=total?(page-1)*pageSize+1:0,to=Math.min(page*pageSize,total);return <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between dark:border-white/10"><p className="text-sm text-slate-500">Showing <b>{from}-{to}</b> of <b>{total}</b></p><div className="flex items-center gap-2"><select value={pageSize} onChange={e=>onSize(Number(e.target.value))} className="h-10 rounded-xl border px-3 text-sm dark:border-white/10 dark:bg-white/5">{[10,20,50,100].map(x=><option key={x}>{x}</option>)}</select><button disabled={page<=1} onClick={()=>onPage(page-1)} className="h-10 rounded-xl border px-3 disabled:opacity-40 dark:border-white/10"><ChevronLeft size={14}/></button><span className="text-xs text-slate-400">Page {page} of {Math.max(totalPages,1)}</span><button disabled={!totalPages||page>=totalPages} onClick={()=>onPage(page+1)} className="h-10 rounded-xl border px-3 disabled:opacity-40 dark:border-white/10"><ChevronRight size={14}/></button></div></div>}
