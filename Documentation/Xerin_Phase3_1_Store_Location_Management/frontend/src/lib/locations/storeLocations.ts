export type StoreCountryOption = {
  value: string;
  label: string;
  scope: "local" | "global";
  apiCountry?: string;
};

export const STORE_COUNTRIES: StoreCountryOption[] = [
  { value: "Tanzania", label: "Tanzania", scope: "local" },
  { value: "United Arab Emirates", label: "United Arab Emirates (Dubai / UAE)", scope: "global", apiCountry: "United Arab Emirates" },
  { value: "China", label: "China", scope: "global", apiCountry: "China" },
  { value: "Turkey", label: "Turkey", scope: "global", apiCountry: "Turkey" },
  { value: "United States", label: "United States of America", scope: "global", apiCountry: "United States" },
  { value: "United Kingdom", label: "United Kingdom", scope: "global", apiCountry: "United Kingdom" },
];

const TZ_GEO_BASE = "https://tzgeodata.vercel.app/api/v1";
const COUNTRIES_NOW_BASE = "https://countriesnow.space/api/v0.1/countries";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Location service returned ${response.status}`);
  return response.json() as Promise<T>;
}

export async function getTanzaniaRegions(): Promise<string[]> {
  const payload = await getJson<{ regions?: string[] }>(`${TZ_GEO_BASE}/regions/`);
  return normalize(payload.regions ?? []);
}

export async function getTanzaniaDistricts(region: string): Promise<string[]> {
  if (!region) return [];
  const payload = await getJson<{ districts?: string[] }>(
    `${TZ_GEO_BASE}/regions/${encodeURIComponent(region)}/districts/`,
  );
  return normalize(payload.districts ?? []);
}

export async function getTanzaniaWards(district: string): Promise<string[]> {
  if (!district) return [];
  const payload = await getJson<{ wards?: string[] }>(
    `${TZ_GEO_BASE}/districts/${encodeURIComponent(district)}/wards/`,
  );
  return normalize(payload.wards ?? []);
}

type CountriesNowStatesResponse = {
  error?: boolean;
  data?: {
    states?: Array<{ name?: string }>;
  };
};

type CountriesNowCitiesResponse = {
  error?: boolean;
  data?: string[];
};

export async function getGlobalStates(country: string): Promise<string[]> {
  if (!country) return [];
  const option = STORE_COUNTRIES.find((item) => item.value === country);
  const apiCountry = option?.apiCountry ?? country;
  const payload = await getJson<CountriesNowStatesResponse>(
    `${COUNTRIES_NOW_BASE}/states/q?country=${encodeURIComponent(apiCountry)}`,
  );
  if (payload.error) return [];
  return normalize((payload.data?.states ?? []).map((item) => item.name ?? ""));
}

export async function getGlobalCities(country: string, state: string): Promise<string[]> {
  if (!country || !state) return [];
  const option = STORE_COUNTRIES.find((item) => item.value === country);
  const apiCountry = option?.apiCountry ?? country;
  const payload = await getJson<CountriesNowCitiesResponse>(
    `${COUNTRIES_NOW_BASE}/state/cities/q?country=${encodeURIComponent(apiCountry)}&state=${encodeURIComponent(state)}`,
  );
  if (payload.error) return [];
  return normalize(payload.data ?? []);
}

function normalize(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
}
