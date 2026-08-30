import { defineStore } from 'pinia'
import { ref } from 'vue'
import { optionsApi } from '@/api'

// 枚举、品牌、型号这类基础字典全站共用一份，避免每个页面各自拉一遍。
export const useMetaStore = defineStore('meta', () => {
  const enums = ref({ statuses: [], media_categories: [], source_platforms: [], currencies: [] })
  const brands = ref([])
  const loaded = ref(false)

  async function ensure() {
    if (loaded.value) return
    await reload()
  }

  async function reload() {
    const [e, b] = await Promise.all([optionsApi.enums(), optionsApi.brands()])
    enums.value = e
    brands.value = b.items || []
    loaded.value = true
  }

  async function reloadBrands() {
    const b = await optionsApi.brands()
    brands.value = b.items || []
  }

  return { enums, brands, loaded, ensure, reload, reloadBrands }
})
