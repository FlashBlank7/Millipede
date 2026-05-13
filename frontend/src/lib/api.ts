import axios from "axios"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
})

api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        window.location.href = "/login"
      }
    }
    return Promise.reject(err)
  }
)

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  register: (email: string, password: string, display_name: string, org_name: string) =>
    api.post("/auth/register", { email, password, display_name, org_name }),
  me: () => api.get("/auth/me"),
}

// Projects
export const projectsApi = {
  create: (data: CreateProjectData) => api.post("/projects", data),
  list: () => api.get("/projects"),
  get: (id: string) => api.get(`/projects/${id}`),
}

// RunCards
export const runcardsApi = {
  submit: (projectId: string) => api.post(`/projects/${projectId}/runcards`),
  list: (projectId: string) => api.get(`/projects/${projectId}/runcards`),
  get: (projectId: string, runcardId: string) =>
    api.get(`/projects/${projectId}/runcards/${runcardId}`),
}

// Uploads
export const uploadsApi = {
  upload: (projectId: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return api.post(`/projects/${projectId}/uploads`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  },
}

// Engineer Reviews
export const reviewsApi = {
  list: () => api.get("/engineer/reviews"),
  outputs: (runcardId: string) => api.get(`/engineer/reviews/${runcardId}/outputs`),
  action: (runcardId: string, action: string, comment?: string, modifications?: Record<string, unknown>) =>
    api.post(`/engineer/reviews/${runcardId}/action`, { action, comment, modifications }),
  dispatch: (runcardId: string) => api.post(`/engineer/reviews/${runcardId}/dispatch`),
}

export interface CreateProjectData {
  product_type: "autoda" | "automl"
  task_level?: "L1" | "L2" | "L3"
  goal: { text: string }
  expected_outputs?: string[]
  success_metric?: Record<string, unknown>
  constraints?: Record<string, unknown>
  raw_dialogue?: string
}
