<template>
  <div class="media-manager">
    <el-alert
      v-if="!hostingConfigured"
      :title="t('media.notConfigured')"
      type="warning"
      :closable="false"
      show-icon
      class="mb"
    />

    <el-tabs v-model="activeCategory" class="cat-tabs">
      <el-tab-pane
        v-for="cat in categories"
        :key="cat"
        :name="cat"
      >
        <template #label>
          <span>{{ t('category.' + cat) }}</span>
          <el-badge
            v-if="countByCategory[cat]"
            :value="countByCategory[cat]"
            class="tab-badge"
            type="primary"
          />
        </template>

        <div class="cat-body">
          <div class="grid">
            <div v-for="item in grouped[cat] || []" :key="item.id" class="cell">
              <div class="thumb" @click="preview(item)">
                <img v-if="item.kind === 'image'" :src="thumbUrl(item)" :alt="item.filename" loading="lazy" />
                <div v-else class="video-thumb">
                  <el-icon :size="30"><VideoPlay /></el-icon>
                  <span class="video-tag">{{ t('media.video') }}</span>
                </div>
              </div>
              <button class="del-btn" type="button" :title="t('common.delete')" @click.stop="removeItem(item)">
                <el-icon><Close /></el-icon>
              </button>
            </div>

            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              :multiple="true"
              :disabled="!canUpload"
              accept="image/*,video/*"
              class="uploader"
              :on-change="(file) => onPick(cat, file)"
            >
              <div class="add-cell" :class="{ disabled: !canUpload }">
                <el-icon :size="24"><Plus /></el-icon>
                <span>{{ uploading ? t('media.uploading') : t('media.upload') }}</span>
              </div>
            </el-upload>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-image-viewer
      v-if="viewerUrls.length"
      :url-list="viewerUrls"
      :initial-index="viewerIndex"
      hide-on-click-modal
      @close="viewerUrls = []"
    />

    <!-- 视频没有图片查看器，单独一个弹窗播放 -->
    <el-dialog v-model="videoDialog" width="720px" :show-close="true" append-to-body class="video-dialog">
      <video v-if="videoUrl" :src="videoUrl" controls autoplay class="video-player" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { mediaApi } from '@/api'
import { ElMessage } from '@/utils/notify'
import { useMetaStore } from '@/stores/meta'

const props = defineProps({
  cardId: { type: Number, required: true },
  hostingConfigured: { type: Boolean, default: true }
})
const emit = defineEmits(['changed'])

const { t } = useI18n()
const meta = useMetaStore()

const categories = computed(() =>
  meta.enums.media_categories?.length
    ? meta.enums.media_categories
    : ['appearance', 'pcb', 'gpu_core', 'gpuz', 'mods']
)
const activeCategory = ref(categories.value[0])
const grouped = ref({})
const uploading = ref(false)

// 一次拖多个文件时 el-upload 会逐个触发 on-change。攒进 buffer，用 microtask
// 合并成一次批量上传请求，而不是每个文件打一次接口。
const pending = { cat: null, files: [] }
let flushScheduled = false

const canUpload = computed(() => props.hostingConfigured && !uploading.value)

const countByCategory = computed(() => {
  const out = {}
  for (const cat of categories.value) out[cat] = (grouped.value[cat] || []).length
  return out
})

const viewerUrls = ref([])
const viewerIndex = ref(0)
const videoDialog = ref(false)
const videoUrl = ref('')

async function load() {
  if (!props.cardId) return
  grouped.value = await mediaApi.listForCard(props.cardId)
}

watch(() => props.cardId, load, { immediate: true })

function thumbUrl(item) {
  // 图床支持 ?w=<档位> 缩略图，列表里用 400 宽的，省流量
  return item.public_url + (item.public_url.includes('?') ? '&' : '?') + 'w=400'
}

function preview(item) {
  if (item.kind === 'video') {
    videoUrl.value = item.public_url
    videoDialog.value = true
    return
  }
  const images = (grouped.value[activeCategory.value] || []).filter((m) => m.kind === 'image')
  viewerUrls.value = images.map((m) => m.public_url)
  viewerIndex.value = Math.max(0, images.findIndex((m) => m.id === item.id))
}

function onPick(cat, file) {
  if (!canUpload.value) return
  pending.cat = cat
  pending.files.push(file.raw)
  if (!flushScheduled) {
    flushScheduled = true
    queueMicrotask(flush)
  }
}

async function flush() {
  flushScheduled = false
  const cat = pending.cat
  const files = pending.files.splice(0)
  if (!files.length) return

  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('card_id', String(props.cardId))
    fd.append('category', cat)
    for (const f of files) fd.append('files', f)
    const res = await mediaApi.upload(fd)
    await load()
    emit('changed')
    if (res.errors?.length) {
      ElMessage.warning(t('media.partialFail', { ok: res.uploaded.length, fail: res.errors.length }))
    } else {
      ElMessage.success(t('media.uploaded', { n: res.uploaded.length }))
    }
  } catch {
    // 拦截器已提示
  } finally {
    uploading.value = false
  }
}

async function removeItem(item) {
  try {
    await mediaApi.remove(item.id, true)
    await load()
    emit('changed')
    ElMessage.success(t('common.deleted'))
  } catch {
    // 拦截器已提示
  }
}

defineExpose({ reload: load })
</script>

<style scoped>
.mb { margin-bottom: 12px; }
.cat-tabs :deep(.el-tabs__item) { color: #a6adb4; }
.tab-badge { margin-left: 6px; }
.cat-body { min-height: 140px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}
.cell {
  position: relative;
  aspect-ratio: 4 / 3;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #28354a;
  background: #0e1830;
}
.thumb { width: 100%; height: 100%; cursor: pointer; }
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.video-thumb {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #8fb8ff;
}
.video-tag { font-size: 12px; color: #a6adb4; }
.del-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.del-btn:hover { background: #f87171; }
.uploader :deep(.el-upload) { width: 100%; display: block; }
.add-cell {
  aspect-ratio: 4 / 3;
  border: 1px dashed #3a4a66;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #8a94a6;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.add-cell:hover { border-color: #5b8cff; color: #8fb8ff; }
.add-cell.disabled { opacity: 0.5; cursor: not-allowed; }
.video-player { width: 100%; max-height: 70vh; border-radius: 8px; }
</style>
