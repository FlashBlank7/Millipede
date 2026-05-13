"use client"

import { useQuery } from "@tanstack/react-query"
import { projectsApi } from "@/lib/api"
import Link from "next/link"

const STATE_BADGE: Record<string, { label: string; color: string }> = {
  DRAFT: { label: "Draft", color: "bg-gray-100 text-gray-600" },
  REQ_READY: { label: "Ready", color: "bg-blue-100 text-blue-700" },
  PRE_ANALYZING: { label: "Analyzing", color: "bg-green-100 text-green-700" },
  PREPROCESSING: { label: "Processing", color: "bg-green-100 text-green-700" },
  DA_PLANNING: { label: "Planning", color: "bg-green-100 text-green-700" },
  DATA_ANALYZING: { label: "Analyzing data", color: "bg-green-100 text-green-700" },
  AWAIT_REVIEW_DA_REPORT: { label: "In review", color: "bg-yellow-100 text-yellow-700" },
  AWAIT_DISPATCH_DA_REPORT: { label: "Awaiting dispatch", color: "bg-purple-100 text-purple-700" },
  PACKAGING: { label: "Packaging", color: "bg-green-100 text-green-700" },
  DELIVERED: { label: "Delivered", color: "bg-gray-100 text-gray-500" },
  FAILED: { label: "Failed", color: "bg-red-100 text-red-700" },
}

export default function CustomerProjectsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
    refetchInterval: 5000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        Loading projects…
      </div>
    )
  }

  const projects: any[] = data || []

  if (projects.length === 0) {
    return (
      <div className="max-w-2xl mx-auto mt-16 text-center">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No projects yet</h2>
        <p className="text-gray-500 mb-6">Submit your first data analysis or ML project.</p>
        <Link
          href="/customer/new"
          className="inline-flex items-center px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 transition-colors"
        >
          New project
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gray-900">My Projects</h1>
        <Link
          href="/customer/new"
          className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 transition-colors"
        >
          New project
        </Link>
      </div>

      <div className="space-y-3">
        {projects.map((p) => {
          const badge = STATE_BADGE[p.status?.toUpperCase()] || { label: p.status, color: "bg-gray-100 text-gray-600" }
          return (
            <Link
              key={p.id}
              href={`/customer/projects/${p.id}`}
              className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-all"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-gray-400">{p.id.slice(0, 8)}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    p.product_type === "autoda"
                      ? "bg-indigo-100 text-indigo-700"
                      : "bg-emerald-100 text-emerald-700"
                  }`}>
                    {p.product_type === "autoda" ? "AutoDA" : "AutoML"}
                  </span>
                  <span className="text-xs text-gray-400">L{p.task_level?.slice(1)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.color}`}>
                    {badge.label}
                  </span>
                  <span className="text-xs text-gray-400">
                    {new Date(p.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
