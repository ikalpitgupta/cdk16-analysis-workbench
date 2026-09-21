const BASE = '/api'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init)
  if (!r.ok) {
    let detail = r.statusText
    try {
      const j = await r.json()
      detail = j.detail ?? JSON.stringify(j)
    } catch { /* non-JSON error */ }
    throw new Error(detail)
  }
  return r.json()
}

export const api = {
  get: <T,>(p: string) => req<T>(p),
  post: <T,>(p: string, body?: unknown) =>
    req<T>(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }),
  put: <T,>(p: string, body: unknown) =>
    req<T>(p, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  del: <T,>(p: string) => req<T>(p, { method: 'DELETE' }),
}

// ---------------- types ----------------
export interface Variant {
  variant_uid: string
  rsid?: string | null
  aa_change?: string | null
  protein_position?: number | null
  variant_class?: string
  domain_name?: string | null
  landmark_type?: string | null
  am_pathogenicity_score?: number | null
  am_pathogenicity_class?: string | null
  conservation_score?: number | null
  priority_score?: number | null
  [k: string]: unknown
}

export interface VariantPage {
  total: number
  page: number
  page_size: number
  pages: number
  variants: Variant[]
}

export interface AnalysisSession {
  id: string
  name: string
  description: string
  status: string
  constraints: Record<string, unknown>
  constraint_hash: string
  created_at: string
  updated_at: string
  runs: { run_number: number; status: string; stage: string; message: string; error: string }[]
  reports: ReportMeta[]
  has_results?: boolean
}

export interface AnalysisResult {
  available: boolean
  analysis_id: string
  analysis_name?: string
  run_number: number
  constraint_hash: string
  constraints: Record<string, unknown>
  summary: { n_available: number; n_matched: number; n_returned: number; n_truncated: boolean; zero_results: boolean }
  statistics: { by_class: Record<string, number>; by_domain: Record<string, number>; by_am_class: Record<string, number>; landmark_counts: Record<string, number> }
  variants: Variant[]
  top_variants: Variant[]
  warnings: string[]
  session_status?: string
  dataset_version?: string
  pipeline_version?: string
  provenance?: Record<string, string>[]
}

export interface ReportMeta {
  id: string
  session_id: string
  run_number: number
  section: string
  version: number
  constraint_hash: string
  status: string
  title: string
  created_at: string
  analysis_name?: string
}

export interface Overview {
  protein: { accession: string; name: string; gene: string; length: number; organism: string; n_features: number; n_domains: number; n_landmarks: number; n_interactions: number; family?: string; function?: string; mw_kda?: number; uniprot_version?: string }
  variants: { total: number; missense: number; with_predictions: number; structurally_mappable: number; by_class: Record<string, number> }
  conservation: { n_positions: number; n_homologs: number; method: string }
  structures: { experimental: string[]; alphafold: string }
  literature_count: number
  clinvar_annotated?: number
  conserved_positions?: number
  spark?: Record<string, number[]>
  dataset_version: string
  pipeline_version: string
}
