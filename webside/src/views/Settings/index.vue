<template>
  <div class="settings-page">
    <h2 class="page-title">{{ t('settings.title') }}</h2>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- 图床 -->
      <el-tab-pane :label="t('settings.tabImageHosting')" name="hosting">
        <el-card shadow="never" class="pane-card">
          <el-form label-width="150px" label-position="left" class="cfg-form">
            <el-form-item :label="t('settings.baseUrl')">
              <el-input v-model="hosting.base_url" placeholder="http://127.0.0.1:9990" />
              <div class="hint">{{ t('settings.baseUrlHint') }}</div>
            </el-form-item>
            <el-form-item :label="t('settings.publicBase')">
              <el-input v-model="hosting.public_base" placeholder="https://images.example.com" />
              <div class="hint">{{ t('settings.publicBaseHint') }}</div>
            </el-form-item>
            <el-form-item :label="t('settings.project')">
              <el-input v-model="hosting.project" placeholder="displaycard" />
              <div class="hint">{{ t('settings.projectHint') }}</div>
            </el-form-item>
            <el-form-item :label="t('settings.token')">
              <el-input v-model="hosting.token" type="password" show-password
                :placeholder="hosting.token_set ? '••••••（' + t('settings.tokenSet') + '）' : t('settings.tokenUnset')" />
              <div class="hint">{{ t('settings.tokenHint') }}</div>
            </el-form-item>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('settings.timeout')">
                  <el-input-number v-model="hosting.timeout" :min="5" :max="600" :controls="false" class="full" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="t('settings.verifyTls')">
                  <el-switch v-model="hosting.verify_tls" />
                </el-form-item>
              </el-col>
            </el-row>
            <div class="form-actions">
              <el-button type="primary" :loading="savingHosting" @click="saveHosting">{{ t('common.save') }}</el-button>
              <el-button :loading="testing" @click="testHosting">{{ t('settings.test') }}</el-button>
            </div>
            <el-alert v-if="testResult" :type="testResult.ok ? 'success' : 'error'" :closable="false" show-icon class="mt">
              <template v-if="testResult.ok">
                {{ t('settings.testOk') }} · {{ t('settings.allowedExt') }}: {{ (testResult.allowed_extensions || []).join(', ') }}
                <template v-if="testResult.max_upload_bytes"> · {{ t('settings.maxUpload') }}: {{ prettySize(testResult.max_upload_bytes) }}</template>
              </template>
              <template v-else>{{ testResult.message }}</template>
            </el-alert>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 数据库 -->
      <el-tab-pane :label="t('settings.tabDatabase')" name="database">
        <el-card shadow="never" class="pane-card">
          <el-alert :title="t('settings.dbHint')" type="info" :closable="false" show-icon class="mb" />
          <div class="kv"><span>{{ t('settings.dbConf') }}</span><b class="dc-mono">{{ db.conf_path }}</b></div>
          <div class="kv"><span>{{ t('settings.dbHost') }}</span><b class="dc-mono">{{ db.host }}:{{ db.port }}</b></div>
          <div class="kv"><span>{{ t('settings.dbName') }}</span><b class="dc-mono">{{ db.database }}</b></div>
          <div class="kv"><span>{{ t('settings.dbUser') }}</span><b class="dc-mono">{{ db.user }}</b></div>
          <div class="kv">
            <span>{{ t('settings.database') }}</span>
            <el-tag :type="db.ok ? 'success' : 'danger'" effect="dark" size="small">
              {{ db.ok ? t('settings.dbConnected') : t('settings.dbDisconnected') }}
            </el-tag>
          </div>
          <div class="kv" v-if="db.version"><span>{{ t('settings.dbVersion') }}</span><b class="dc-mono">{{ db.version }}</b></div>
          <div class="kv" v-if="db.error"><span class="dc-loss">Error</span><b class="dc-loss">{{ db.error }}</b></div>
          <div class="form-actions">
            <el-button :icon="Refresh" :loading="reconnecting" @click="reconnect">{{ t('settings.dbReconnect') }}</el-button>
          </div>
          <el-table v-if="db.tables?.length" :data="db.tables" size="small" class="mt">
            <el-table-column prop="name" :label="t('settings.dbTables')" />
            <el-table-column align="right" width="140">
              <template #default="{ row }"><span class="dc-dim dc-mono">{{ t('settings.dbRows', { n: row.approx_rows ?? 0 }) }}</span></template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 品牌 / 型号 -->
      <el-tab-pane :label="t('settings.tabDict')" name="dict">
        <el-row :gutter="16">
          <el-col :xs="24" :md="10">
            <el-card shadow="never" class="pane-card">
              <template #header>{{ t('settings.brands') }}</template>
              <div class="add-row">
                <el-input v-model="newBrand" :placeholder="t('settings.brandName')" @keyup.enter="addBrand" />
                <el-button type="primary" :icon="Plus" @click="addBrand" />
              </div>
              <div class="chip-list">
                <el-tag
                  v-for="b in meta.brands"
                  :key="b.id"
                  closable
                  class="chip"
                  @close="removeBrand(b)"
                >{{ b.name }}</el-tag>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="14">
            <el-card shadow="never" class="pane-card">
              <template #header>{{ t('settings.models') }}</template>
              <div class="add-row model-add">
                <el-select v-model="modelBrandId" :placeholder="t('settings.selectBrand')" clearable class="mb-select" @change="loadModels">
                  <el-option v-for="b in meta.brands" :key="b.id" :label="b.name" :value="b.id" />
                </el-select>
                <el-input v-model="newModel" :placeholder="t('settings.modelName')" @keyup.enter="addModel" />
                <el-input v-model="newModelVram" :placeholder="t('settings.defaultVram')" class="vram-in" />
                <el-button type="primary" :icon="Plus" @click="addModel" />
              </div>
              <el-table :data="models" size="small" max-height="360">
                <el-table-column prop="name" :label="t('settings.modelName')" />
                <el-table-column prop="brand_name" :label="t('settings.brands')" width="120" />
                <el-table-column prop="default_vram" :label="t('settings.defaultVram')" width="100" />
                <el-table-column width="60">
                  <template #default="{ row }">
                    <el-button size="small" text type="danger" :icon="Delete" @click="removeModel(row)" />
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 账号 -->
      <el-tab-pane :label="t('settings.tabAccount')" name="account">
        <el-card shadow="never" class="pane-card account-card">
          <template #header>{{ t('settings.changePwd') }}</template>
          <el-form ref="pwdFormRef" :model="pwd" :rules="pwdRules" label-width="130px" label-position="left">
            <el-form-item :label="t('settings.oldPwd')" prop="old_password">
              <el-input v-model="pwd.old_password" type="password" show-password />
            </el-form-item>
            <el-form-item :label="t('settings.newPwd')" prop="new_password">
              <el-input v-model="pwd.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item :label="t('settings.confirmPwd')" prop="confirm">
              <el-input v-model="pwd.confirm" type="password" show-password @keyup.enter="changePwd" />
            </el-form-item>
            <el-button type="primary" :loading="changingPwd" @click="changePwd">{{ t('settings.changePwd') }}</el-button>
          </el-form>

          <el-divider />
          <el-form label-width="130px" label-position="left">
            <el-form-item :label="t('settings.language')">
              <el-select :model-value="locale" @change="setLocale">
                <el-option v-for="opt in localeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { authApi, optionsApi, systemApi } from '@/api'
import { ElMessage } from '@/utils/notify'
import { currentLocale, localeOptions, setLocale } from '@/i18n'
import { useMetaStore } from '@/stores/meta'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const meta = useMetaStore()
const auth = useAuthStore()
const locale = currentLocale

const activeTab = ref('hosting')

// ---- 图床 ----
const hosting = reactive({ base_url: '', public_base: '', project: '', token: '', token_set: false, timeout: 30, verify_tls: true })
const savingHosting = ref(false)
const testing = ref(false)
const testResult = ref(null)

async function loadHosting() {
  const cfg = await systemApi.getImageHosting()
  Object.assign(hosting, cfg, { token: '' })
}
async function saveHosting() {
  savingHosting.value = true
  try {
    const payload = { ...hosting }
    delete payload.token_set
    delete payload.configured
    delete payload.media_count
    if (!payload.token) delete payload.token // 空表示不改
    const cfg = await systemApi.saveImageHosting(payload)
    Object.assign(hosting, cfg, { token: '' })
    ElMessage.success(t('common.saved'))
  } catch { /* 拦截器已提示 */ } finally {
    savingHosting.value = false
  }
}
async function testHosting() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = { ok: true, ...(await systemApi.testImageHosting()) }
  } catch (e) {
    testResult.value = { ok: false, message: e?.response?.data?.detail || t('settings.testFail') }
  } finally {
    testing.value = false
  }
}
function prettySize(bytes) {
  if (!bytes) return '—'
  const mb = bytes / 1024 / 1024
  return mb >= 1 ? mb.toFixed(0) + ' MB' : (bytes / 1024).toFixed(0) + ' KB'
}

// ---- 数据库 ----
const db = reactive({ conf_path: '', host: '', port: '', database: '', user: '', ok: false, version: '', error: '', tables: [] })
const reconnecting = ref(false)

async function loadDb() {
  try {
    Object.assign(db, await systemApi.databaseStatus())
  } catch { /* 非管理员会 403，忽略 */ }
}
async function reconnect() {
  reconnecting.value = true
  try {
    await systemApi.databaseReconnect()
    ElMessage.success(t('settings.dbConnected'))
    await loadDb()
  } catch { /* 拦截器已提示 */ } finally {
    reconnecting.value = false
  }
}

// ---- 品牌 / 型号 ----
const newBrand = ref('')
const newModel = ref('')
const newModelVram = ref('')
const modelBrandId = ref(null)
const models = ref([])

async function addBrand() {
  const name = newBrand.value.trim()
  if (!name) return
  await optionsApi.createBrand({ name })
  newBrand.value = ''
  await meta.reloadBrands()
}
async function removeBrand(b) {
  await optionsApi.removeBrand(b.id)
  await meta.reloadBrands()
}
async function loadModels() {
  const res = await optionsApi.models(modelBrandId.value || undefined)
  models.value = res.items || []
}
async function addModel() {
  const name = newModel.value.trim()
  if (!name) return
  await optionsApi.createModel({ name, brand_id: modelBrandId.value || null, default_vram: newModelVram.value.trim() || null })
  newModel.value = ''
  newModelVram.value = ''
  await loadModels()
}
async function removeModel(row) {
  await optionsApi.removeModel(row.id)
  await loadModels()
}

// ---- 改密码 ----
const pwdFormRef = ref()
const pwd = reactive({ old_password: '', new_password: '', confirm: '' })
const changingPwd = ref(false)
const pwdRules = {
  old_password: [{ required: true, trigger: 'blur', message: ' ' }],
  new_password: [{ required: true, min: 8, trigger: 'blur', message: t('settings.pwdRule') }],
  confirm: [{
    validator: (_r, v, cb) => (v === pwd.new_password ? cb() : cb(new Error(t('settings.pwdMismatch')))),
    trigger: 'blur'
  }]
}
async function changePwd() {
  await pwdFormRef.value?.validate(async (valid) => {
    if (!valid) return
    changingPwd.value = true
    try {
      await authApi.changePassword({ old_password: pwd.old_password, new_password: pwd.new_password })
      ElMessage.success(t('settings.pwdChanged'))
      setTimeout(() => auth.logout(), 1200)
    } catch { /* 拦截器已提示 */ } finally {
      changingPwd.value = false
    }
  })
}

onMounted(async () => {
  await meta.ensure()
  loadHosting()
  loadDb()
  loadModels()
})
</script>

<style scoped>
.page-title { font-size: 20px; margin-bottom: 16px; }
.pane-card { margin-bottom: 16px; }
.cfg-form .hint { font-size: 12px; color: #7b8698; margin-top: 4px; line-height: 1.5; }
.full { width: 100% !important; }
.form-actions { margin-top: 12px; }
.mt { margin-top: 12px; }
.mb { margin-bottom: 12px; }
.kv { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #1c2740; font-size: 14px; }
.kv span { color: #8a94a6; }
.kv b { color: #e6edf7; font-weight: 500; word-break: break-all; text-align: right; }
.add-row { display: flex; gap: 8px; margin-bottom: 14px; }
.model-add { flex-wrap: wrap; }
.mb-select { width: 130px !important; }
.vram-in { width: 110px !important; flex: 0 0 110px; }
.chip-list { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { margin: 0; }
.account-card { max-width: 520px; }
</style>
