"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { projectsApi, uploadsApi } from "@/lib/api"
import { toast } from "sonner"

const PRODUCT_OPTIONS = [
  {
    value: "autoda",
    label: "分析数据，理解业务规律",
    sublabel: "AutoDA — 自动数据分析",
    desc: "AI 自动完成数据清洗、统计分析、可视化，交付完整分析报告。",
  },
  {
    value: "automl",
    label: "训练模型，得到可部署方案",
    sublabel: "AutoML — 自动机器学习",
    desc: "AI 自动完成特征工程、模型选择、训练和评估，交付可部署的模型服务。",
  },
]

const ALLOWED_TYPES = [
  "text/csv",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/pdf",
]

export default function NewProjectPage() {
  const router = useRouter()
  const [step, setStep] = useState<"product" | "goal" | "data" | "confirm">("product")
  const [productType, setProductType] = useState<"autoda" | "automl">("autoda")
  const [goal, setGoal] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [projectId, setProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleCreate() {
    setLoading(true)
    try {
      const { data: project } = await projectsApi.create({
        product_type: productType,
        task_level: "L1",
        goal: { text: goal },
      })
      setProjectId(project.id)

      for (const file of files) {
        await uploadsApi.upload(project.id, file)
      }

      setStep("confirm")
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to create project")
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit() {
    if (!projectId) return
    setLoading(true)
    try {
      const { runcardsApi } = await import("@/lib/api")
      await runcardsApi.submit(projectId)
      toast.success("Project submitted! AI is now working on it.")
      router.push(`/customer/projects/${projectId}`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Submission failed")
    } finally {
      setLoading(false)
    }
  }

  const dropHandler = (e: React.DragEvent) => {
    e.preventDefault()
    const dropped = Array.from(e.dataTransfer.files).filter((f) => ALLOWED_TYPES.includes(f.type))
    setFiles((prev) => [...prev, ...dropped])
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          {(["product", "goal", "data", "confirm"] as const).map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                step === s ? "bg-gray-900 text-white" :
                ["product","goal","data","confirm"].indexOf(s) < ["product","goal","data","confirm"].indexOf(step)
                  ? "bg-gray-300 text-gray-600" : "border border-gray-200 text-gray-400"
              }`}>{i + 1}</div>
              {i < 3 && <div className="w-8 h-px bg-gray-200" />}
            </div>
          ))}
        </div>
        <h1 className="text-xl font-semibold text-gray-900 mt-4">New Project</h1>
      </div>

      {step === "product" && (
        <div className="space-y-4">
          <p className="text-sm text-gray-600 mb-4">你想做什么？</p>
          {PRODUCT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setProductType(opt.value as "autoda" | "automl")}
              className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                productType === opt.value
                  ? "border-gray-900 bg-gray-50"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <div className="font-medium text-gray-900">{opt.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{opt.sublabel}</div>
              <div className="text-sm text-gray-600 mt-1">{opt.desc}</div>
            </button>
          ))}
          <div className="pt-2">
            <button
              onClick={() => setStep("goal")}
              className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 transition-colors"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {step === "goal" && (
        <div className="space-y-4">
          <p className="text-sm text-gray-600">描述你的分析目标和问题</p>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="例如：分析过去一年的销售数据，找出销量下滑的主要原因，并识别高价值客户群体的特征。"
            rows={6}
            className="w-full rounded-xl border border-gray-200 p-3 text-sm outline-none focus:ring-2 focus:ring-gray-900 resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => setStep("product")}
              className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
            >
              Back
            </button>
            <button
              disabled={!goal.trim()}
              onClick={() => setStep("data")}
              className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-40 transition-colors"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {step === "data" && (
        <div className="space-y-4">
          <p className="text-sm text-gray-600">上传你的数据文件（csv、xlsx、xls、pdf）</p>

          <div
            onDrop={dropHandler}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-gray-300 transition-colors"
          >
            <div className="text-gray-400 text-sm mb-2">拖拽文件到此处，或</div>
            <label className="cursor-pointer text-sm font-medium text-gray-900 underline-offset-2 hover:underline">
              点击选择文件
              <input
                type="file"
                multiple
                accept=".csv,.xlsx,.xls,.pdf"
                className="hidden"
                onChange={(e) => {
                  const selected = Array.from(e.target.files || []).filter((f) => ALLOWED_TYPES.includes(f.type))
                  setFiles((prev) => [...prev, ...selected])
                }}
              />
            </label>
            <div className="text-xs text-gray-400 mt-2">单文件最大 500MB</div>
          </div>

          {productType === "automl" && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
              如果你计划进行机器学习训练，请注意：传统机器学习模型通常需要数千条以上记录，深度学习模型需要更大量级的数据。平台会在分析阶段评估数据充足性。
            </div>
          )}

          {files.length > 0 && (
            <div className="space-y-2">
              {files.map((f, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 text-sm">
                  <span className="text-gray-700 truncate">{f.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 text-xs">{(f.size / 1024 / 1024).toFixed(1)} MB</span>
                    <button
                      onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                      className="text-gray-400 hover:text-red-500 text-xs"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={() => setStep("goal")}
              className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
            >
              Back
            </button>
            <button
              onClick={handleCreate}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-40 transition-colors"
            >
              {loading ? "Creating…" : files.length === 0 ? "Continue without data" : "Create project"}
            </button>
          </div>
        </div>
      )}

      {step === "confirm" && (
        <div className="space-y-4 text-center">
          <div className="text-4xl mb-4">✓</div>
          <h2 className="text-lg font-semibold text-gray-900">Project created</h2>
          <p className="text-sm text-gray-600">点击下方按钮提交项目，AI 将立即开始分析。</p>
          <div className="bg-gray-50 rounded-xl p-4 text-left text-sm space-y-2">
            <div className="flex gap-2"><span className="text-gray-400 w-20">类型</span><span className="font-medium">{productType === "autoda" ? "AutoDA" : "AutoML"}</span></div>
            <div className="flex gap-2"><span className="text-gray-400 w-20">目标</span><span className="text-gray-700 flex-1">{goal.slice(0, 80)}{goal.length > 80 ? "…" : ""}</span></div>
            <div className="flex gap-2"><span className="text-gray-400 w-20">文件</span><span className="text-gray-700">{files.length} 个</span></div>
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-6 py-2.5 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-40 transition-colors"
          >
            {loading ? "Submitting…" : "Submit to AI"}
          </button>
        </div>
      )}
    </div>
  )
}
