"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { api } from "@/lib/api"

interface RunCardSummary {
  id: string
  project_id: string
  current_state: string
  kind: string
  created_at: string
}

const STATE_LABEL: Record<string, string> = {
  AWAIT_REVIEW_DA_REPORT: "Awaiting Review",
  AWAIT_DISPATCH_DA_REPORT: "Awaiting Dispatch",
}

export default function ReviewsPage() {
  const [runcards, setRuncards] = useState<RunCardSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    const load = () =>
      api.get("/engineer/reviews")
        .then((r) => setRuncards(r.data))
        .catch(() => setError("Failed to load reviews"))
        .finally(() => setLoading(false))

    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  if (loading) return <p className="text-gray-500">Loading…</p>
  if (error) return <p className="text-red-500">{error}</p>

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">Pending Reviews</h1>
      {runcards.length === 0 ? (
        <p className="text-gray-400 text-sm">No runcards awaiting review.</p>
      ) : (
        <div className="space-y-3">
          {runcards.map((rc) => (
            <Link
              key={rc.id}
              href={`/engineer/reviews/${rc.id}`}
              className="block bg-white border rounded-lg px-5 py-4 hover:shadow-sm transition"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-mono text-gray-700">{rc.id}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Project: {rc.project_id} · {rc.kind}
                  </p>
                </div>
                <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full">
                  {STATE_LABEL[rc.current_state] ?? rc.current_state}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
