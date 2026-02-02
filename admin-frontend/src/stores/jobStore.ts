import { create } from 'zustand'
import type { Job } from '@/api/client'

interface JobState {
  jobs: Job[]
  activeJobId: string | null
  setJobs: (jobs: Job[]) => void
  setActiveJobId: (id: string | null) => void
  updateJob: (id: string, updates: Partial<Job>) => void
}

export const useJobStore = create<JobState>((set) => ({
  jobs: [],
  activeJobId: null,
  setJobs: (jobs) => set({ jobs }),
  setActiveJobId: (id) => set({ activeJobId: id }),
  updateJob: (id, updates) =>
    set((state) => ({
      jobs: state.jobs.map((job) =>
        job.id === id ? { ...job, ...updates } : job
      ),
    })),
}))
