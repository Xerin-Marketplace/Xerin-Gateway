"use client";

import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  Banknote,
  Building2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Globe2,
  Landmark,
  PackageCheck,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Truck,
  UserPlus,
} from "lucide-react";

import {
  type AdminCommissionRule,
  type AdminEscrowHold,
  type AdminFinanceSettings,
  type AdminLogisticsCompany,
  type AdminLogisticsIntegration,
  type AdminLogisticsRate,
  type AdminLogisticsService,
  type AdminLogisticsZone,
  type AdminMarketplaceSettings,
  createCommissionRule,
  onboardLogisticsCompany,
  createLogisticsRate,
  createLogisticsService,
  createLogisticsZone,
  deactivateLogisticsCompany,
  deactivateLogisticsRate,
  deactivateLogisticsService,
  deactivateLogisticsZone,
  deleteCommissionRule,
  disputeEscrowHold,
  getFinanceSettings,
  getLogisticsIntegration,
  getMarketplaceSettings,
  listCommissionRules,
  listEscrowHolds,
  listLogisticsCompanies,
  listLogisticsRates,
  listLogisticsServices,
  listLogisticsZones,
  releaseEscrowHold,
  saveLogisticsIntegration,
  saveMarketplaceSettings,
  updateCommissionRule,
  updateFinanceSettings,
} from "@/lib/api/endpoints/admin";

export type AdminConfigurationView =
  | "marketplace"
  | "commissions"
  | "logistics-companies"
  | "logistics-services"
  | "logistics-zones"
  | "logistics-rates"
  | "logistics-integration"
  | "finance-settings"
  | "escrow";

const titles: Record<AdminConfigurationView, [string, string, string]> = {
  marketplace: [
    "Marketplace governance",
    "Marketplace Settings",
    "Control escrow timing, dispute window, cash-on-delivery and international delivery from one backend-backed configuration.",
  ],
  commissions: [
    "Marketplace economics",
    "Commission Rules",
    "Configure global, category, seller and product-specific commissions. The backend resolves the most specific applicable rule.",
  ],
  "logistics-companies": [
    "Logistics network",
    "Logistics Companies",
    "Register delivery companies that can be offered to customers during local or international checkout.",
  ],
  "logistics-services": [
    "Logistics network",
    "Delivery Services",
    "Create Standard, Express, Same-day or International services and connect them to a logistics company.",
  ],
  "logistics-zones": [
    "Delivery coverage",
    "Shipping Zones",
    "Define countries, regions and cities where logistics services are available.",
  ],
  "logistics-rates": [
    "Delivery pricing",
    "Shipping Rates",
    "Configure service prices by zone, currency, weight and free-shipping threshold.",
  ],
  "logistics-integration": [
    "Provider integration",
    "API & Webhook Configuration",
    "Configure logistics API and webhook metadata without exposing raw provider secrets in the frontend.",
  ],
  "finance-settings": [
    "Financial configuration",
    "Finance Settings",
    "Control settlement currency, payout rules and escrow behaviour while payment-provider operations remain in the Payments module.",
  ],
  escrow: [
    "Financial control",
    "Escrow Holds",
    "Inspect money held for orders, freeze disputed holds and release eligible funds using permission-controlled actions.",
  ],
};

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const errorMessage = (error: unknown) => {
  const candidate = error as {
    response?: { data?: { detail?: string | { msg?: string }[] } };
    message?: string;
  };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return candidate.message || "Request failed.";
};

const inputClass =
  "h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-50";
const textareaClass =
  "min-h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-50";

export default function AdminConfiguration({
  view,
}: {
  view: AdminConfigurationView;
}) {
  const [eyebrow, title, description] = titles[view];

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f47524]">
          {eyebrow}
        </p>
        <h2 className="mt-1 text-2xl font-bold tracking-[-0.02em] text-slate-900">
          {title}
        </h2>
        <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-500">
          {description}
        </p>
      </section>

      {view === "marketplace" && <MarketplaceSettings />}
      {view === "commissions" && <CommissionRules />}
      {view === "logistics-companies" && <LogisticsCompanies />}
      {view === "logistics-services" && <LogisticsServices />}
      {view === "logistics-zones" && <LogisticsZones />}
      {view === "logistics-rates" && <LogisticsRates />}
      {view === "logistics-integration" && <LogisticsIntegration />}
      {view === "finance-settings" && <FinanceSettings />}
      {view === "escrow" && <EscrowHolds />}
    </div>
  );
}

function MarketplaceSettings() {
  const [form, setForm] = useState({
    escrow_release_hours: 48,
    dispute_period_hours: 48,
    cod_allowed: false,
    international_delivery_allowed: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [configured, setConfigured] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getMarketplaceSettings();
      setConfigured(data.configured);
      if (data.configured) {
        setForm({
          escrow_release_hours: data.escrow_release_hours ?? 48,
          dispute_period_hours: data.dispute_period_hours ?? 48,
          cod_allowed: Boolean(data.cod_allowed),
          international_delivery_allowed: Boolean(data.international_delivery_allowed),
        });
      }
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await saveMarketplaceSettings(form);
      setConfigured(true);
      toast.success("Marketplace settings saved.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Loading label="Loading marketplace settings..." />;

  return (
    <>
      {!configured && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          These marketplace business rules have not been configured yet. Save the
          settings below before Customer checkout depends on them.
        </div>
      )}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card title="Escrow & Disputes" icon={ShieldCheck}>
          <Field label="Escrow release period (hours)">
            <input
              type="number"
              min={1}
              max={720}
              className={inputClass}
              value={form.escrow_release_hours}
              onChange={(e) =>
                setForm((x) => ({ ...x, escrow_release_hours: Number(e.target.value) }))
              }
            />
          </Field>
          <Field label="Dispute period (hours)">
            <input
              type="number"
              min={1}
              max={720}
              className={inputClass}
              value={form.dispute_period_hours}
              onChange={(e) =>
                setForm((x) => ({ ...x, dispute_period_hours: Number(e.target.value) }))
              }
            />
          </Field>
        </Card>

        <Card title="Checkout Rules" icon={Settings2}>
          <Toggle
            label="Cash on Delivery"
            hint="Allow COD as a checkout payment option where supported."
            checked={form.cod_allowed}
            onChange={(value) => setForm((x) => ({ ...x, cod_allowed: value }))}
          />
          <Toggle
            label="International Delivery"
            hint="Permit shipping quotes outside Tanzania."
            checked={form.international_delivery_allowed}
            onChange={(value) =>
              setForm((x) => ({ ...x, international_delivery_allowed: value }))
            }
          />
        </Card>
      </section>

      <button
        onClick={() => void save()}
        disabled={saving}
        className="rounded-xl bg-[#f47524] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save Marketplace Settings"}
      </button>
    </>
  );
}

function CommissionRules() {
  const [rows, setRows] = useState<AdminCommissionRule[]>([]);
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [meta, setMeta] = useState({ total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    name: "Default marketplace commission",
    scope: "global",
    rule_type: "percentage",
    rate: 2,
    target_id: "",
    priority: 0,
  });

  const load = async () => {
    setLoading(true);
    try {
      const data = await listCommissionRules({
        page,
        page_size: pageSize,
        search: search || undefined,
        scope: scope === "all" ? undefined : scope,
      });
      setRows(data.results);
      setMeta({ total: data.total, total_pages: data.total_pages });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => void load(), 250);
    return () => clearTimeout(timer);
  }, [page, pageSize, search, scope]);

  const create = async () => {
    const target =
      form.scope === "seller"
        ? { seller_id: form.target_id }
        : form.scope === "category"
          ? { category_id: form.target_id }
          : form.scope === "product"
            ? { product_id: form.target_id }
            : {};

    try {
      await createCommissionRule({
        name: form.name.trim(),
        scope: form.scope,
        rule_type: form.rule_type,
        rate: form.rate,
        priority: form.priority,
        is_active: true,
        ...target,
      });
      toast.success("Commission rule created.");
      await load();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  return (
    <section className="grid gap-5 xl:grid-cols-[390px_1fr]">
      <Card title="Add Commission Rule" icon={CircleDollarSign}>
        <Field label="Rule name">
          <input className={inputClass} value={form.name} onChange={(e) => setForm((x) => ({ ...x, name: e.target.value }))} />
        </Field>
        <Field label="Scope">
          <select className={inputClass} value={form.scope} onChange={(e) => setForm((x) => ({ ...x, scope: e.target.value, target_id: "" }))}>
            <option value="global">Global default</option>
            <option value="category">Category</option>
            <option value="seller">Seller</option>
            <option value="product">Product override</option>
          </select>
        </Field>
        {form.scope !== "global" && (
          <Field label={`${pretty(form.scope)} UUID`}>
            <input className={inputClass} placeholder="Paste target UUID" value={form.target_id} onChange={(e) => setForm((x) => ({ ...x, target_id: e.target.value.trim() }))} />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <select className={inputClass} value={form.rule_type} onChange={(e) => setForm((x) => ({ ...x, rule_type: e.target.value }))}>
              <option value="percentage">Percentage</option>
              <option value="fixed">Fixed</option>
            </select>
          </Field>
          <Field label="Rate">
            <input type="number" min={0} step="0.01" className={inputClass} value={form.rate} onChange={(e) => setForm((x) => ({ ...x, rate: Number(e.target.value) }))} />
          </Field>
        </div>
        <Field label="Priority">
          <input type="number" className={inputClass} value={form.priority} onChange={(e) => setForm((x) => ({ ...x, priority: Number(e.target.value) }))} />
        </Field>
        <button onClick={() => void create()} className="w-full rounded-xl bg-[#f47524] py-3 text-sm font-semibold text-white">
          Create Commission Rule
        </button>
      </Card>

      <TableCard
        title="Commission rules"
        search={search}
        setSearch={(v) => { setSearch(v); setPage(1); }}
        filter={
          <select className={inputClass} value={scope} onChange={(e) => { setScope(e.target.value); setPage(1); }}>
            <option value="all">All scopes</option>
            <option value="global">Global</option>
            <option value="category">Category</option>
            <option value="seller">Seller</option>
            <option value="product">Product</option>
          </select>
        }
      >
        {loading ? <Loading label="Loading commission rules..." /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <TableHead headers={["Rule", "Scope", "Type", "Rate", "Priority", "Status", "Actions"]} />
                <tbody className="divide-y divide-slate-100">
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td className="px-5 py-4 font-semibold text-slate-800">{row.name}</td>
                      <td className="px-5 py-4">{pretty(row.scope)}</td>
                      <td className="px-5 py-4">{pretty(row.rule_type)}</td>
                      <td className="px-5 py-4 font-semibold">{row.rate}{row.rule_type === "percentage" ? "%" : ""}</td>
                      <td className="px-5 py-4">{row.priority}</td>
                      <td className="px-5 py-4"><Status value={row.is_active ? "active" : "inactive"} /></td>
                      <td className="px-5 py-4">
                        <div className="flex gap-2">
                          <button className="text-xs font-semibold text-slate-600" onClick={async () => {
                            await updateCommissionRule(row.id, { is_active: !row.is_active });
                            await load();
                          }}>{row.is_active ? "Disable" : "Enable"}</button>
                          <button className="text-xs font-semibold text-red-600" onClick={async () => {
                            if (!confirm("Delete this commission rule?")) return;
                            await deleteCommissionRule(row.id);
                            await load();
                          }}>Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!rows.length && <EmptyRow colSpan={7} text="No commission rules found." />}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={pageSize} total={meta.total} totalPages={meta.total_pages} setPage={setPage} setPageSize={setPageSize} />
          </>
        )}
      </TableCard>
    </section>
  );
}

function LogisticsCompanies() {
  const [rows, setRows] = useState<AdminLogisticsCompany[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [meta, setMeta] = useState({ total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  type LogisticsCompanyForm = {
    name: string;
    code: string;
    admin_first_name: string;
    admin_last_name: string;
    admin_email: string;
    admin_phone: string;
    temporary_password: string;
    scope: AdminLogisticsCompany["scope"];
    status: AdminLogisticsCompany["status"];
    supports_cod: boolean;
    supports_tracking: boolean;
    supports_webhooks: boolean;
  };
  const [form, setForm] = useState<LogisticsCompanyForm>({
    name: "", code: "", admin_first_name: "", admin_last_name: "", admin_email: "",
    admin_phone: "", temporary_password: "", scope: "local", status: "pending",
    supports_cod: false, supports_tracking: true,
    supports_webhooks: false,
  });
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await listLogisticsCompanies({ page, page_size: pageSize, search: search || undefined });
      setRows(data.results); setMeta({ total: data.total, total_pages: data.total_pages });
    } catch (error) { toast.error(errorMessage(error)); }
    finally { setLoading(false); }
  };
  useEffect(() => { const t = setTimeout(() => void load(), 250); return () => clearTimeout(t); }, [page, pageSize, search]);

  const create = async () => {
    if (creating) return;
    if (!form.name.trim() || !form.code.trim() || !form.admin_first_name.trim() ||
        !form.admin_last_name.trim() || !form.admin_email.trim() || form.temporary_password.length < 8) {
      toast.error("Complete the company and administrator fields. Password must be at least 8 characters.");
      return;
    }
    setCreating(true);
    try {
      const result = await onboardLogisticsCompany({
        company: {
          name: form.name.trim(), code: form.code.trim(),
          contact_name: `${form.admin_first_name} ${form.admin_last_name}`.trim(),
          contact_email: form.admin_email.trim(), contact_phone: form.admin_phone.trim() || null,
          scope: form.scope, status: "pending", supports_cod: form.supports_cod,
          supports_tracking: form.supports_tracking, supports_webhooks: form.supports_webhooks,
          metadata_json: {},
        },
        administrator: {
          first_name: form.admin_first_name.trim(), last_name: form.admin_last_name.trim(),
          email: form.admin_email.trim(), phone: form.admin_phone.trim() || null,
          password: form.temporary_password,
        },
      });
      if (result.welcome_email_sent) toast.success("Company administrator created and welcome email sent.");
      else toast.error(result.warning || "Account created, but the welcome email was not sent.");
      setForm((x) => ({ ...x, name: "", code: "", admin_first_name: "", admin_last_name: "",
        admin_email: "", admin_phone: "", temporary_password: "" }));
      await load();
    } catch (error) { toast.error(errorMessage(error)); }
    finally { setCreating(false); }
  };

  return (
    <section className="grid gap-5 xl:grid-cols-[390px_1fr]">
      <Card title="Register Logistics Company" icon={Building2}>
        <div className="mb-4 rounded-xl border border-blue-100 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
          This creates the company and its primary administrator. The company starts pending and receives onboarding instructions by email.
        </div>
        <Field label="Company name"><input required className={inputClass} value={form.name} onChange={(e) => setForm((x) => ({...x, name:e.target.value}))} /></Field>
        <Field label="Company code"><input required className={inputClass} placeholder="e.g. dhl-tanzania" value={form.code} onChange={(e) => setForm((x) => ({...x, code:e.target.value.toLowerCase().replace(/[^a-z0-9_-]+/g,"-").replace(/^-+|-+$/g,"")}))} /></Field>
        <div className="my-4 flex items-center gap-2 border-t pt-4 text-sm font-bold text-slate-800"><UserPlus size={17}/>Primary company administrator</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="First name"><input required className={inputClass} value={form.admin_first_name} onChange={(e) => setForm((x) => ({...x, admin_first_name:e.target.value}))} /></Field>
          <Field label="Last name"><input required className={inputClass} value={form.admin_last_name} onChange={(e) => setForm((x) => ({...x, admin_last_name:e.target.value}))} /></Field>
        </div>
        <Field label="Login email"><input required type="email" autoComplete="off" className={inputClass} value={form.admin_email} onChange={(e) => setForm((x) => ({...x, admin_email:e.target.value}))} /></Field>
        <Field label="Phone (optional)"><input type="tel" className={inputClass} value={form.admin_phone} onChange={(e) => setForm((x) => ({...x, admin_phone:e.target.value}))} /></Field>
        <Field label="Temporary password"><input required type="password" minLength={8} maxLength={72} autoComplete="new-password" className={inputClass} value={form.temporary_password} onChange={(e) => setForm((x) => ({...x, temporary_password:e.target.value}))} /></Field>
        <p className="-mt-2 mb-3 text-xs leading-5 text-slate-500">Share the temporary password securely. It is never included in the welcome email.</p>
        <Field label="Delivery scope">
          <select className={inputClass} value={form.scope} onChange={(e) => setForm((x) => ({...x, scope:e.target.value as AdminLogisticsCompany["scope"]}))}>
            <option value="local">Tanzania / Local</option>
            <option value="international">International</option>
            <option value="both">Local + International</option>
          </select>
        </Field>
        <Toggle label="Supports COD" checked={form.supports_cod} onChange={(v) => setForm((x) => ({...x, supports_cod:v}))} />
        <Toggle label="Supports Tracking" checked={form.supports_tracking} onChange={(v) => setForm((x) => ({...x, supports_tracking:v}))} />
        <Toggle label="Webhook Integration" checked={form.supports_webhooks} onChange={(v) => setForm((x) => ({...x, supports_webhooks:v}))} />
        <button disabled={creating} onClick={() => void create()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#f47524] py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60">{creating && <RefreshCw className="animate-spin" size={16}/>} {creating ? "Creating company…" : "Create Company & Administrator"}</button>
      </Card>

      <TableCard title="Registered logistics companies" search={search} setSearch={(v) => {setSearch(v);setPage(1);}}>
        {loading ? <Loading label="Loading logistics companies..." /> : <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <TableHead headers={["Company", "Contact", "Scope", "COD", "Tracking", "Status", "Actions"]} />
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => <tr key={row.id}>
                  <td className="px-5 py-4"><b>{row.name}</b><p className="text-xs text-slate-400">{row.code}</p></td>
                  <td className="px-5 py-4"><p>{row.contact_name || "—"}</p><p className="text-xs text-slate-400">{row.contact_email || row.contact_phone || "—"}</p></td>
                  <td className="px-5 py-4">{pretty(row.scope)}</td>
                  <td className="px-5 py-4">{row.supports_cod ? "Yes" : "No"}</td>
                  <td className="px-5 py-4">{row.supports_tracking ? "Yes" : "No"}</td>
                  <td className="px-5 py-4"><Status value={row.status} /></td>
                  <td className="px-5 py-4">
                    <button className="text-xs font-semibold text-red-600" onClick={async () => {
                      if (!confirm("Deactivate this logistics company?")) return;
                      await deactivateLogisticsCompany(row.id); await load();
                    }}>Deactivate</button>
                  </td>
                </tr>)}
                {!rows.length && <EmptyRow colSpan={7} text="No logistics companies registered." />}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pageSize={pageSize} total={meta.total} totalPages={meta.total_pages} setPage={setPage} setPageSize={setPageSize}/>
        </>}
      </TableCard>
    </section>
  );
}

function LogisticsServices() {
  const [companies, setCompanies] = useState<AdminLogisticsCompany[]>([]);
  const [rows, setRows] = useState<AdminLogisticsService[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [meta, setMeta] = useState({ total: 0, total_pages: 0 });
  type LogisticsServiceForm = {
    logistics_company_id: string; name: string; service_code: string;
    scope: AdminLogisticsService["scope"];
    supports_cod: boolean; supports_tracking: boolean;
    min_delivery_days: number; max_delivery_days: number;
  };
  const [form, setForm] = useState<LogisticsServiceForm>({
    logistics_company_id: "", name: "", service_code: "", scope: "local",
    supports_cod:false, supports_tracking:true, min_delivery_days:1, max_delivery_days:3,
  });
  const load = async () => {
    try {
      const [c, s] = await Promise.all([
        listLogisticsCompanies({ page:1, page_size:100, status:"active" }),
        listLogisticsServices({ page, page_size:pageSize, search:search||undefined }),
      ]);
      setCompanies(c.results); setRows(s.results); setMeta({total:s.total,total_pages:s.total_pages});
    } catch(error){ toast.error(errorMessage(error)); }
  };
  useEffect(() => { const t=setTimeout(()=>void load(),250); return()=>clearTimeout(t); },[page,pageSize,search]);

  return <section className="grid gap-5 xl:grid-cols-[390px_1fr]">
    <Card title="Create Delivery Service" icon={Truck}>
      <Field label="Logistics company"><select className={inputClass} value={form.logistics_company_id} onChange={(e)=>setForm(x=>({...x,logistics_company_id:e.target.value}))}><option value="">Select company</option>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
      <Field label="Service name"><input className={inputClass} placeholder="Express Delivery" value={form.name} onChange={(e)=>setForm(x=>({...x,name:e.target.value}))}/></Field>
      <Field label="Service code"><input className={inputClass} placeholder="EXPRESS-TZ" value={form.service_code} onChange={(e)=>setForm(x=>({...x,service_code:e.target.value}))}/></Field>
      <Field label="Scope"><select className={inputClass} value={form.scope} onChange={(e)=>setForm(x=>({...x,scope:e.target.value as AdminLogisticsService["scope"]}))}><option value="local">Local</option><option value="international">International</option><option value="both">Both</option></select></Field>
      <div className="grid grid-cols-2 gap-3"><Field label="Min days"><input type="number" min={0} className={inputClass} value={form.min_delivery_days} onChange={(e)=>setForm(x=>({...x,min_delivery_days:Number(e.target.value)}))}/></Field><Field label="Max days"><input type="number" min={0} className={inputClass} value={form.max_delivery_days} onChange={(e)=>setForm(x=>({...x,max_delivery_days:Number(e.target.value)}))}/></Field></div>
      <Toggle label="Supports COD" checked={form.supports_cod} onChange={(v)=>setForm(x=>({...x,supports_cod:v}))}/>
      <Toggle label="Supports Tracking" checked={form.supports_tracking} onChange={(v)=>setForm(x=>({...x,supports_tracking:v}))}/>
      <button className="w-full rounded-xl bg-[#f47524] py-3 text-sm font-semibold text-white" onClick={async()=>{try{await createLogisticsService({...form,is_active:true});toast.success("Service created.");await load();}catch(e){toast.error(errorMessage(e));}}}>Create Service</button>
    </Card>
    <TableCard title="Delivery services" search={search} setSearch={(v)=>{setSearch(v);setPage(1);}}>
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><TableHead headers={["Service","Company","Scope","ETA","COD","Tracking","Action"]}/><tbody className="divide-y">{rows.map(r=><tr key={r.id}><td className="px-5 py-4"><b>{r.name}</b><p className="text-xs text-slate-400">{r.service_code||"—"}</p></td><td className="px-5 py-4">{companies.find(c=>c.id===r.logistics_company_id)?.name||r.carrier_name||"—"}</td><td className="px-5 py-4">{pretty(r.scope)}</td><td className="px-5 py-4">{r.min_delivery_days}-{r.max_delivery_days} days</td><td className="px-5 py-4">{r.supports_cod?"Yes":"No"}</td><td className="px-5 py-4">{r.supports_tracking?"Yes":"No"}</td><td className="px-5 py-4"><button className="text-xs font-semibold text-red-600" onClick={async()=>{await deactivateLogisticsService(r.id);await load();}}>Deactivate</button></td></tr>)}{!rows.length&&<EmptyRow colSpan={7} text="No delivery services found."/>}</tbody></table></div>
      <Pagination page={page} pageSize={pageSize} total={meta.total} totalPages={meta.total_pages} setPage={setPage} setPageSize={setPageSize}/>
    </TableCard>
  </section>;
}

function LogisticsZones() {
  const [rows,setRows]=useState<AdminLogisticsZone[]>([]);
  const [search,setSearch]=useState(""); const [page,setPage]=useState(1); const [pageSize,setPageSize]=useState(10);
  const [meta,setMeta]=useState({total:0,total_pages:0});
  const [form,setForm]=useState<{name:string;country:string;scope:AdminLogisticsZone["scope"];regions:string;cities:string}>({name:"",country:"Tanzania",scope:"local",regions:"",cities:""});
  const load=async()=>{try{const r=await listLogisticsZones({page,page_size:pageSize,search:search||undefined});setRows(r.results);setMeta({total:r.total,total_pages:r.total_pages});}catch(e){toast.error(errorMessage(e));}};
  useEffect(()=>{const t=setTimeout(()=>void load(),250);return()=>clearTimeout(t)},[page,pageSize,search]);
  const split=(v:string)=>v.split(",").map(x=>x.trim()).filter(Boolean);
  return <section className="grid gap-5 xl:grid-cols-[390px_1fr]"><Card title="Create Shipping Zone" icon={Globe2}>
    <Field label="Zone name"><input className={inputClass} value={form.name} onChange={e=>setForm(x=>({...x,name:e.target.value}))}/></Field>
    <Field label="Country"><input className={inputClass} value={form.country} onChange={e=>setForm(x=>({...x,country:e.target.value}))}/></Field>
    <Field label="Scope"><select className={inputClass} value={form.scope} onChange={e=>setForm(x=>({...x,scope:e.target.value as AdminLogisticsZone["scope"]}))}><option value="local">Local</option><option value="international">International</option><option value="both">Both</option></select></Field>
    <Field label="Regions (comma-separated)"><textarea className={textareaClass} value={form.regions} onChange={e=>setForm(x=>({...x,regions:e.target.value}))}/></Field>
    <Field label="Cities (comma-separated)"><textarea className={textareaClass} value={form.cities} onChange={e=>setForm(x=>({...x,cities:e.target.value}))}/></Field>
    <button className="w-full rounded-xl bg-[#f47524] py-3 text-sm font-semibold text-white" onClick={async()=>{try{await createLogisticsZone({name:form.name,country:form.country,scope:form.scope,regions:split(form.regions),cities:split(form.cities),is_active:true});toast.success("Zone created.");await load();}catch(e){toast.error(errorMessage(e));}}}>Create Zone</button>
  </Card><TableCard title="Shipping zones" search={search} setSearch={v=>{setSearch(v);setPage(1);}}>
    <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><TableHead headers={["Zone","Country","Scope","Regions","Cities","Status","Action"]}/><tbody className="divide-y">{rows.map(r=><tr key={r.id}><td className="px-5 py-4 font-semibold">{r.name}</td><td className="px-5 py-4">{r.country}</td><td className="px-5 py-4">{pretty(r.scope)}</td><td className="px-5 py-4">{r.regions.join(", ")||"All"}</td><td className="px-5 py-4">{r.cities.join(", ")||"All"}</td><td className="px-5 py-4"><Status value={r.is_active?"active":"inactive"}/></td><td className="px-5 py-4"><button className="text-xs font-semibold text-red-600" onClick={async()=>{await deactivateLogisticsZone(r.id);await load();}}>Deactivate</button></td></tr>)}{!rows.length&&<EmptyRow colSpan={7} text="No shipping zones found."/>}</tbody></table></div>
    <Pagination page={page} pageSize={pageSize} total={meta.total} totalPages={meta.total_pages} setPage={setPage} setPageSize={setPageSize}/>
  </TableCard></section>;
}

function LogisticsRates() {
  const [companies,setCompanies]=useState<AdminLogisticsCompany[]>([]);
  const [services,setServices]=useState<AdminLogisticsService[]>([]);
  const [zones,setZones]=useState<AdminLogisticsZone[]>([]);
  const [rows,setRows]=useState<AdminLogisticsRate[]>([]);
  const [search,setSearch]=useState(""); const [page,setPage]=useState(1); const [pageSize,setPageSize]=useState(10);
  const [meta,setMeta]=useState({total:0,total_pages:0});
  const [form,setForm]=useState<{zone_id:string;method_id:string;rate_type:AdminLogisticsRate["rate_type"];currency:string;base_amount:number;amount_per_kg:number;min_weight_kg:string;max_weight_kg:string;free_shipping_threshold:string}>({zone_id:"",method_id:"",rate_type:"flat",currency:"TZS",base_amount:0,amount_per_kg:0,min_weight_kg:"",max_weight_kg:"",free_shipping_threshold:""});
  const load=async()=>{try{const [c,s,z,r]=await Promise.all([listLogisticsCompanies({page:1,page_size:100,status:"active"}),listLogisticsServices({page:1,page_size:100,active:true}),listLogisticsZones({page:1,page_size:100,active:true}),listLogisticsRates({page,page_size:pageSize,search:search||undefined})]);setCompanies(c.results);setServices(s.results);setZones(z.results);setRows(r.results);setMeta({total:r.total,total_pages:r.total_pages});}catch(e){toast.error(errorMessage(e));}};
  useEffect(()=>{const t=setTimeout(()=>void load(),250);return()=>clearTimeout(t)},[page,pageSize,search]);
  return <section className="grid gap-5 xl:grid-cols-[390px_1fr]"><Card title="Create Shipping Rate" icon={Banknote}>
    <Field label="Shipping zone"><select className={inputClass} value={form.zone_id} onChange={e=>setForm(x=>({...x,zone_id:e.target.value}))}><option value="">Select zone</option>{zones.map(z=><option key={z.id} value={z.id}>{z.name}</option>)}</select></Field>
    <Field label="Delivery service"><select className={inputClass} value={form.method_id} onChange={e=>setForm(x=>({...x,method_id:e.target.value}))}><option value="">Select service</option>{services.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
    <div className="grid grid-cols-2 gap-3"><Field label="Rate type"><select className={inputClass} value={form.rate_type} onChange={e=>setForm(x=>({...x,rate_type:e.target.value as AdminLogisticsRate["rate_type"]}))}><option value="flat">Flat</option><option value="weight_based">Weight based</option><option value="free">Free</option></select></Field><Field label="Currency"><select className={inputClass} value={form.currency} onChange={e=>setForm(x=>({...x,currency:e.target.value}))}><option>TZS</option><option>USD</option></select></Field></div>
    <div className="grid grid-cols-2 gap-3"><Field label="Base amount"><input type="number" min={0} className={inputClass} value={form.base_amount} onChange={e=>setForm(x=>({...x,base_amount:Number(e.target.value)}))}/></Field><Field label="Per KG"><input type="number" min={0} className={inputClass} value={form.amount_per_kg} onChange={e=>setForm(x=>({...x,amount_per_kg:Number(e.target.value)}))}/></Field></div>
    <Field label="Free shipping threshold"><input type="number" min={0} className={inputClass} value={form.free_shipping_threshold} onChange={e=>setForm(x=>({...x,free_shipping_threshold:e.target.value}))}/></Field>
    <button className="w-full rounded-xl bg-[#f47524] py-3 text-sm font-semibold text-white" onClick={async()=>{try{await createLogisticsRate({zone_id:form.zone_id,method_id:form.method_id,rate_type:form.rate_type,currency:form.currency,base_amount:form.base_amount,amount_per_kg:form.amount_per_kg,free_shipping_threshold:form.free_shipping_threshold?Number(form.free_shipping_threshold):null,is_active:true});toast.success("Shipping rate created.");await load();}catch(e){toast.error(errorMessage(e));}}}>Create Rate</button>
  </Card><TableCard title="Shipping rates" search={search} setSearch={v=>{setSearch(v);setPage(1);}}>
    <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><TableHead headers={["Provider / Service","Zone","Type","Base","Per KG","Currency","Action"]}/><tbody className="divide-y">{rows.map(r=><tr key={r.id}><td className="px-5 py-4"><b>{r.method.name}</b><p className="text-xs text-slate-400">{companies.find(c=>c.id===r.method.logistics_company_id)?.name||r.method.carrier_name||"—"}</p></td><td className="px-5 py-4">{r.zone.name}</td><td className="px-5 py-4">{pretty(r.rate_type)}</td><td className="px-5 py-4 font-semibold">{r.base_amount.toLocaleString()}</td><td className="px-5 py-4">{r.amount_per_kg.toLocaleString()}</td><td className="px-5 py-4">{r.currency}</td><td className="px-5 py-4"><button className="text-xs font-semibold text-red-600" onClick={async()=>{await deactivateLogisticsRate(r.id);await load();}}>Deactivate</button></td></tr>)}{!rows.length&&<EmptyRow colSpan={7} text="No shipping rates found."/>}</tbody></table></div>
    <Pagination page={page} pageSize={pageSize} total={meta.total} totalPages={meta.total_pages} setPage={setPage} setPageSize={setPageSize}/>
  </TableCard></section>;
}

function LogisticsIntegration() {
  const [companies,setCompanies]=useState<AdminLogisticsCompany[]>([]);
  const [companyId,setCompanyId]=useState("");
  const [form,setForm]=useState<{api_base_url:string;outbound_webhook_url:string;auth_type:AdminLogisticsIntegration["auth_type"];credential_reference:string;webhook_secret_reference:string;api_key_header:string;is_active:boolean}>({api_base_url:"",outbound_webhook_url:"",auth_type:"none",credential_reference:"",webhook_secret_reference:"",api_key_header:"",is_active:false});
  useEffect(()=>{void listLogisticsCompanies({page:1,page_size:100}).then(r=>{setCompanies(r.results);if(r.results[0])setCompanyId(r.results[0].id);}).catch(e=>toast.error(errorMessage(e)))},[]);
  useEffect(()=>{if(!companyId)return;void getLogisticsIntegration(companyId).then(r=>setForm({api_base_url:r.api_base_url||"",outbound_webhook_url:r.outbound_webhook_url||"",auth_type:r.auth_type,credential_reference:r.credential_reference||"",webhook_secret_reference:r.webhook_secret_reference||"",api_key_header:r.api_key_header||"",is_active:r.is_active})).catch(()=>setForm({api_base_url:"",outbound_webhook_url:"",auth_type:"none",credential_reference:"",webhook_secret_reference:"",api_key_header:"",is_active:false}))},[companyId]);
  return <section className="grid gap-5 lg:grid-cols-[300px_1fr]"><Card title="Logistics Company" icon={Building2}><Field label="Company"><select className={inputClass} value={companyId} onChange={e=>setCompanyId(e.target.value)}>{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><p className="text-xs leading-5 text-slate-500">Credentials are stored as environment/secret references. Do not paste raw API secrets into these fields.</p></Card><Card title="API / Webhook Configuration" icon={Settings2}>
    <Field label="API base URL"><input className={inputClass} placeholder="https://provider.example/api" value={form.api_base_url} onChange={e=>setForm(x=>({...x,api_base_url:e.target.value}))}/></Field>
    <Field label="Outbound webhook URL"><input className={inputClass} placeholder="https://provider.example/webhooks/xerin" value={form.outbound_webhook_url} onChange={e=>setForm(x=>({...x,outbound_webhook_url:e.target.value}))}/></Field>
    <Field label="Authentication"><select className={inputClass} value={form.auth_type} onChange={e=>setForm(x=>({...x,auth_type:e.target.value as AdminLogisticsIntegration["auth_type"]}))}><option value="none">None</option><option value="api_key">API Key</option><option value="bearer">Bearer</option><option value="basic">Basic</option><option value="oauth2">OAuth2</option><option value="custom">Custom</option></select></Field>
    <Field label="Credential environment reference"><input className={inputClass} placeholder="DHL_API_KEY" value={form.credential_reference} onChange={e=>setForm(x=>({...x,credential_reference:e.target.value}))}/></Field>
    <Field label="Webhook secret reference"><input className={inputClass} placeholder="DHL_WEBHOOK_SECRET" value={form.webhook_secret_reference} onChange={e=>setForm(x=>({...x,webhook_secret_reference:e.target.value}))}/></Field>
    <Field label="API-key header"><input className={inputClass} placeholder="X-API-Key" value={form.api_key_header} onChange={e=>setForm(x=>({...x,api_key_header:e.target.value}))}/></Field>
    <Toggle label="Integration active" checked={form.is_active} onChange={v=>setForm(x=>({...x,is_active:v}))}/>
    <button disabled={!companyId} className="rounded-xl bg-[#f47524] px-5 py-3 text-sm font-semibold text-white disabled:opacity-40" onClick={async()=>{try{await saveLogisticsIntegration(companyId,{...form,extra_config:{}});toast.success("Integration configuration saved.");}catch(e){toast.error(errorMessage(e));}}}>Save Integration</button>
  </Card></section>;
}

function FinanceSettings() {
  const [form,setForm]=useState<AdminFinanceSettings|null>(null);
  const [loading,setLoading]=useState(true); const [saving,setSaving]=useState(false);
  const load=async()=>{setLoading(true);try{setForm(await getFinanceSettings());}catch(e){toast.error(errorMessage(e));}finally{setLoading(false);}};
  useEffect(()=>{void load()},[]);
  if(loading||!form)return <Loading label="Loading finance settings..."/>;
  return <section className="grid gap-4 lg:grid-cols-2"><Card title="Settlement & Payouts" icon={Landmark}>
    <Field label="Default payment provider code"><input className={inputClass} value={form.default_payment_provider_code||""} onChange={e=>setForm({...form,default_payment_provider_code:e.target.value})}/></Field>
    <Field label="Settlement currency"><select className={inputClass} value={form.settlement_currency} onChange={e=>setForm({...form,settlement_currency:e.target.value})}><option>TZS</option><option>USD</option></select></Field>
    <Field label="Minimum payout amount"><input type="number" min={0} className={inputClass} value={form.minimum_payout_amount} onChange={e=>setForm({...form,minimum_payout_amount:Number(e.target.value)})}/></Field>
    <div className="grid grid-cols-2 gap-3"><Field label="Payout fee type"><select className={inputClass} value={form.payout_fee_type} onChange={e=>setForm({...form,payout_fee_type:e.target.value as "fixed"|"percentage"})}><option value="fixed">Fixed</option><option value="percentage">Percentage</option></select></Field><Field label="Payout fee"><input type="number" min={0} className={inputClass} value={form.payout_fee_value} onChange={e=>setForm({...form,payout_fee_value:Number(e.target.value)})}/></Field></div>
    <Field label="Processing days"><input type="number" min={0} max={90} className={inputClass} value={form.payout_processing_days} onChange={e=>setForm({...form,payout_processing_days:Number(e.target.value)})}/></Field>
    <Toggle label="Automatic payouts" checked={form.auto_payout_enabled} onChange={v=>setForm({...form,auto_payout_enabled:v})}/>
  </Card><Card title="Escrow Behaviour" icon={ShieldCheck}>
    <Toggle label="Escrow enabled" checked={form.escrow_enabled} onChange={v=>setForm({...form,escrow_enabled:v})}/>
    <Toggle label="Automatic release" checked={form.auto_release_enabled} onChange={v=>setForm({...form,auto_release_enabled:v})}/>
    <Toggle label="Allow partial release" checked={form.allow_partial_release} onChange={v=>setForm({...form,allow_partial_release:v})}/>
    <Toggle label="Hold Xerin commission until release" checked={form.hold_commission_until_release} onChange={v=>setForm({...form,hold_commission_until_release:v})}/>
    <div className="rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-500">Marketplace Settings controls <b>when</b> a hold is eligible for release. Finance Settings controls <b>how</b> settlement and payout behaviour operates.</div>
    <button disabled={saving} className="w-full rounded-xl bg-[#f47524] py-3 text-sm font-semibold text-white disabled:opacity-50" onClick={async()=>{setSaving(true);try{const {id,singleton_key,created_at,updated_at,...payload}=form;setForm(await updateFinanceSettings(payload));toast.success("Finance settings saved.");}catch(e){toast.error(errorMessage(e));}finally{setSaving(false)}}}>{saving?"Saving...":"Save Finance Settings"}</button>
  </Card></section>;
}

function EscrowHolds() {
  const [rows,setRows]=useState<AdminEscrowHold[]>([]); const [search,setSearch]=useState(""); const [status,setStatus]=useState("all");
  const [page,setPage]=useState(1); const [pageSize,setPageSize]=useState(10); const [meta,setMeta]=useState({total:0,total_pages:0}); const [loading,setLoading]=useState(true);
  const load=async()=>{setLoading(true);try{const r=await listEscrowHolds({page,page_size:pageSize,search:search||undefined,status:status==="all"?undefined:status});setRows(r.results);setMeta({total:r.total,total_pages:r.total_pages});}catch(e){toast.error(errorMessage(e));}finally{setLoading(false)}};
  useEffect(()=>{const t=setTimeout(()=>void load(),250);return()=>clearTimeout(t)},[page,pageSize,search,status]);
  return <TableCard title="Escrow ledger" search={search} setSearch={v=>{setSearch(v);setPage(1);}} filter={<select className={inputClass} value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="all">All statuses</option><option value="held">Held</option><option value="release_pending">Release pending</option><option value="disputed">Disputed</option><option value="released">Released</option><option value="refunded">Refunded</option></select>}>
    {loading?<Loading label="Loading escrow holds..."/>:<><div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-left text-sm"><TableHead headers={["Reference","Order","Seller","Gross","Seller","Commission","Released","Status","Actions"]}/><tbody className="divide-y">{rows.map(r=><tr key={r.id}><td className="px-5 py-4 font-mono text-xs">{r.reference}</td><td className="px-5 py-4 font-mono text-xs">{r.order_id.slice(0,8)}…</td><td className="px-5 py-4 font-mono text-xs">{r.seller_id?r.seller_id.slice(0,8)+"…":"—"}</td><td className="px-5 py-4 font-semibold">{r.gross_amount.toLocaleString()} {r.currency}</td><td className="px-5 py-4">{r.seller_amount.toLocaleString()}</td><td className="px-5 py-4">{r.commission_amount.toLocaleString()}</td><td className="px-5 py-4">{r.released_amount.toLocaleString()}</td><td className="px-5 py-4"><Status value={r.status}/></td><td className="px-5 py-4"><div className="flex gap-2">{["held","release_pending"].includes(r.status)&&<><button className="text-xs font-semibold text-emerald-700" onClick={async()=>{const amountText=prompt("Release amount (leave empty for full remaining amount):");const note=prompt("Release note (optional):")||undefined;try{await releaseEscrowHold(r.id,amountText?Number(amountText):undefined,note);toast.success("Escrow release recorded.");await load();}catch(e){toast.error(errorMessage(e));}}}>Release</button><button className="text-xs font-semibold text-red-600" onClick={async()=>{const note=prompt("Dispute reason:");if(!note)return;try{await disputeEscrowHold(r.id,note);toast.success("Escrow marked disputed.");await load();}catch(e){toast.error(errorMessage(e));}}}>Dispute</button></>}</div></td></tr>)}{!rows.length&&<EmptyRow colSpan={9} text="No escrow holds found yet. Holds will populate after Customer payment allocation is connected."/>}</tbody></table></div><Pagination page={page} pageSize={pageSize} total={meta.total} totalPages={meta.total_pages} setPage={setPage} setPageSize={setPageSize}/></>}
  </TableCard>;
}

function Card({title,icon:Icon,children}:{title:string;icon:any;children:React.ReactNode}) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]"><Icon size={17}/></span><h3 className="font-bold text-slate-900">{title}</h3></div><div className="space-y-4">{children}</div></section>;
}
function Field({label,children}:{label:string;children:React.ReactNode}){return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}</span>{children}</label>}
function Toggle({label,hint,checked,onChange}:{label:string;hint?:string;checked:boolean;onChange:(v:boolean)=>void}){return <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border border-slate-200 p-4"><span><span className="block text-sm font-semibold text-slate-800">{label}</span>{hint&&<span className="mt-0.5 block text-xs text-slate-500">{hint}</span>}</span><input type="checkbox" checked={checked} onChange={e=>onChange(e.target.checked)} className="h-5 w-5 accent-[#f47524]"/></label>}
function TableCard({title,search,setSearch,filter,children}:{title:string;search:string;setSearch:(v:string)=>void;filter?:React.ReactNode;children:React.ReactNode}){return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex flex-col gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-bold text-slate-900">{title}</h3></div><div className="flex flex-col gap-2 sm:flex-row"><label className="relative"><Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"/><input className={`${inputClass} min-w-[260px] pl-10`} value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search..."/></label>{filter}</div></div>{children}</section>}
function TableHead({headers}:{headers:string[]}){return <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wide text-slate-500"><tr>{headers.map(h=><th key={h} className="px-5 py-3.5">{h}</th>)}</tr></thead>}
function EmptyRow({colSpan,text}:{colSpan:number;text:string}){return <tr><td colSpan={colSpan} className="px-5 py-10 text-center text-sm text-slate-500">{text}</td></tr>}
function Status({value}:{value:string}){const green=["active","released","completed","verified"].includes(value.toLowerCase());const red=["inactive","suspended","disputed","rejected","failed"].includes(value.toLowerCase());return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${green?"border-emerald-200 bg-emerald-50 text-emerald-700":red?"border-red-200 bg-red-50 text-red-700":"border-amber-200 bg-amber-50 text-amber-700"}`}>{pretty(value)}</span>}
function Loading({label}:{label:string}){return <div className="p-12 text-center text-sm text-slate-500"><RefreshCw size={20} className="mx-auto animate-spin"/><p className="mt-3">{label}</p></div>}
function Pagination({page,pageSize,total,totalPages,setPage,setPageSize}:{page:number;pageSize:number;total:number;totalPages:number;setPage:(p:number)=>void;setPageSize:(s:number)=>void}){const from=total?(page-1)*pageSize+1:0;const to=Math.min(page*pageSize,total);return <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><p className="text-sm text-slate-500">Showing <b>{from}-{to}</b> of <b>{total}</b></p><div className="flex items-center gap-2"><select className="h-10 rounded-xl border border-slate-200 px-3 text-sm" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1)}}>{[10,20,50,100].map(s=><option key={s} value={s}>{s} / page</option>)}</select><button disabled={page<=1} onClick={()=>setPage(page-1)} className="inline-flex h-10 items-center gap-1 rounded-xl border border-slate-200 px-3 text-sm font-semibold disabled:opacity-40"><ChevronLeft size={14}/>Previous</button><span className="min-w-20 text-center text-xs text-slate-500">Page {page} of {Math.max(1,totalPages)}</span><button disabled={page>=totalPages||!totalPages} onClick={()=>setPage(page+1)} className="inline-flex h-10 items-center gap-1 rounded-xl border border-slate-200 px-3 text-sm font-semibold disabled:opacity-40">Next<ChevronRight size={14}/></button></div></div>}
