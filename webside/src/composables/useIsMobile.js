import { onMounted, onUnmounted, ref } from 'vue'

// 断点 768px，与 App.vue 里的 @media (max-width: 768px) 同一口径——
// 两边不一致时，恰好 768px 宽的设备会一半按手机、一半按电脑渲染。
export function useIsMobile() {
  const isMobile = ref(false)
  let mq = null

  const update = (e) => { isMobile.value = e.matches }

  onMounted(() => {
    mq = window.matchMedia('(max-width: 768px)')
    isMobile.value = mq.matches
    mq.addEventListener('change', update)
  })
  onUnmounted(() => {
    if (mq) mq.removeEventListener('change', update)
  })

  return { isMobile }
}
