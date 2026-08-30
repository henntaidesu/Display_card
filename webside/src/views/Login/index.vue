<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <div class="title-wrap">
          <div class="title-wrap__left">
            <el-icon size="26"><UserFilled /></el-icon>
            <span>{{ t('login.title') }}</span>
          </div>
          <el-select
            :model-value="locale"
            size="small"
            class="login-lang-switcher"
            @change="onLocaleChange"
          >
            <el-option
              v-for="opt in localeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>
      </template>

      <!-- 关闭浏览器账号密码自动填充：密码框用 new-password（Chrome 忽略 off 但认它） -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        autocomplete="off"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            :placeholder="t('login.placeholderUser')"
            size="large"
            clearable
            autocomplete="off"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="t('login.placeholderPwd')"
            size="large"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button native-type="submit" type="primary" size="large" :loading="loading" style="width: 100%">
            {{ t('login.submit') }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="tip">{{ t('login.defaultAccount') }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { currentLocale, localeOptions, setLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const locale = currentLocale
const loading = ref(false)
const formRef = ref()
const form = reactive({ username: '', password: '' })

const rules = computed(() => ({
  username: [{ required: true, message: t('login.placeholderUser'), trigger: 'blur' }],
  password: [{ required: true, message: t('login.placeholderPwd'), trigger: 'blur' }]
}))

function onLocaleChange(val) {
  setLocale(val)
}

async function handleLogin() {
  // 校验不过时 validate() 会 reject——单独 try 住，不让它把后面的登录流程也带崩
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    // 正常用 router 跳；个别情况下（并发导航/守卫）router.replace 会静默失败，
    // 兜底直接改 hash 强制跳转，保证登录后一定离开登录页。
    try {
      await router.replace('/dashboard')
    } catch {
      window.location.hash = '#/dashboard'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100 * var(--app-vh));
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at top, #1f2a44 0%, #0b1220 55%);
  padding: 16px;
  position: relative;
}

.login-card {
  width: 100%;
  max-width: 520px;
  border: 1px solid #2a3446;
}

.title-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 18px;
  font-weight: 600;
  color: #b8c4d0;
}

.title-wrap__left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  white-space: nowrap;
}

.login-lang-switcher {
  width: 130px;
  flex-shrink: 0;
}

/* 覆盖 App.vue 中 .el-input { width: 180px } 的全局规则 */
.login-card :deep(.el-form .el-input) {
  width: 100% !important;
}

.tip {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}

@media (max-width: 768px) {
  .login-page {
    padding: max(16px, env(safe-area-inset-top, 0px))
             max(16px, env(safe-area-inset-right, 0px))
             max(16px, env(safe-area-inset-bottom, 0px))
             max(16px, env(safe-area-inset-left, 0px));
  }
  .login-lang-switcher {
    width: 110px !important;
    min-width: 0;
  }
  .title-wrap { gap: 8px; font-size: 16px; }
  .title-wrap__left {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
