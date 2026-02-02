import { create } from 'zustand'
import type { ConfigEntry } from '@/api/client'

interface ConfigState {
  selectedCrawlerConfig: string | null
  selectedIndexerConfig: string | null
  crawlerConfigs: ConfigEntry[]
  indexerConfigs: ConfigEntry[]
  setSelectedCrawlerConfig: (name: string | null) => void
  setSelectedIndexerConfig: (name: string | null) => void
  setCrawlerConfigs: (configs: ConfigEntry[]) => void
  setIndexerConfigs: (configs: ConfigEntry[]) => void
}

export const useConfigStore = create<ConfigState>((set) => ({
  selectedCrawlerConfig: null,
  selectedIndexerConfig: null,
  crawlerConfigs: [],
  indexerConfigs: [],
  setSelectedCrawlerConfig: (name) => set({ selectedCrawlerConfig: name }),
  setSelectedIndexerConfig: (name) => set({ selectedIndexerConfig: name }),
  setCrawlerConfigs: (configs) => set({ crawlerConfigs: configs }),
  setIndexerConfigs: (configs) => set({ indexerConfigs: configs }),
}))
