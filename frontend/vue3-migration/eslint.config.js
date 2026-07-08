import pluginVue from 'eslint-plugin-vue';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import vueTsConfig from '@vue/eslint-config-typescript';
import prettierConfig from '@vue/eslint-config-prettier';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig([
  // 全局忽略
  globalIgnores(['dist/**', 'node_modules/**', '*.config.js', '*.config.ts']),

  // 基础 + Vue 规则
  ...pluginVue.configs['flat/recommended'],
  ...vueTsConfig(),
  prettierConfig,

  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
  },

  // TypeScript 文件规则
  {
    files: ['**/*.ts', '**/*.tsx'],
    plugins: {
      '@typescript-eslint': tsPlugin,
    },
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: false,
      },
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {
          prefer: 'type-imports',
        },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },

  // Vue 文件规则
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tsParser,
      },
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/require-default-prop': 'off',
      'vue/no-v-html': 'warn',
      'vue/component-name-in-template-casing': ['error', 'PascalCase'],
      'vue/attribute-hyphenation': ['error', 'always'],
      'vue/html-self-closing': [
        'error',
        {
          html: {
            void: 'always',
            normal: 'always',
            component: 'always',
          },
          svg: 'always',
          math: 'always',
        },
      ],
      'vue/order-in-components': 'error',
      'vue/component-api-style': ['error', ['script-setup']],
    },
  },

  // 通用 JS/TS 规则
  {
    files: ['**/*.{js,mjs,cjs,ts,mts,cts,jsx,tsx,vue}'],
    rules: {
      'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
      'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
      'prefer-const': 'error',
      'no-var': 'error',
      'eqeqeq': ['error', 'always'],
    },
  },
]);
