<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <img src="/static/logo.svg" alt="logo" class="brand-logo" />
        <div>
          <h1 class="brand-title">{{ t('app.name') }}</h1>
          <p class="brand-sub">{{ t('login.subtitle') }}</p>
        </div>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="onSubmit">
        <el-form-item :label="t('login.username')" prop="username">
          <el-input v-model="form.username" size="large" :placeholder="t('login.placeholderUser')" clearable>
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item :label="t('login.password')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            :placeholder="t('login.placeholderPwd')"
            show-password
            @keyup.enter="onSubmit"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" size="large" class="submit" :loading="loading" @click="onSubmit">
          {{ t('login.submit') }}
        </el-button>
      </el-form>

      <p class="hint">{{ t('login.firstRun') }}</p>

      <div class="lang-switch">
        <el-radio-group :model-value="locale" size="small" @change="setLocale">
          <el-radio-button v-for="opt in localeOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
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
const form = reactive({ username: 'admin', password: '' })

const rules = {
  username: [{ required: true, message: t('login.placeholderUser'), trigger: 'blur' }],
  password: [{ required: true, message: t('login.placeholderPwd'), trigger: 'blur' }]
}

async function onSubmit() {
  await formRef.value?.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await auth.login(form.username, form.password)
      router.push('/dashboard')
    } catch {
      // http 拦截器已弹错
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 600px at 20% -10%, rgba(91,140,255,0.18), transparent),
    radial-gradient(1000px 500px at 100% 110%, rgba(124,92,255,0.16), transparent),
    #0b1220;
  padding: 20px;
}
.login-card {
  width: 100%;
  max-width: 400px;
  background: #131c2f;
  border: 1px solid #28354a;
  border-radius: 16px;
  padding: 32px 28px 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}
.brand-logo { width: 46px; height: 46px; }
.brand-title { font-size: 20px; color: #e6edf7; margin: 0; }
.brand-sub { font-size: 13px; color: #8a94a6; margin: 4px 0 0; }
.submit { width: 100%; margin-top: 4px; }
.hint {
  margin-top: 18px;
  font-size: 12px;
  color: #7b8698;
  line-height: 1.6;
  text-align: center;
}
.lang-switch { margin-top: 16px; display: flex; justify-content: center; }
</style>
