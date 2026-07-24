<!--
  伏羲 v2.1 — 节点属性编辑器
  在右侧面板显示选中节点的可编辑属性
-->
<template>
  <div class="node-property-editor">
    <div class="property-content">
      <!-- 基本信息 -->
      <PropertySection title="基本信息">
        <PropertyField label="节点名称">
          <input
            class="prop-input"
            :value="node.label"
            @input="updateField('label', ($event.target as HTMLInputElement).value)"
          />
        </PropertyField>

        <PropertyField label="节点ID">
          <span class="prop-readonly">{{ node.id }}</span>
        </PropertyField>

        <PropertyField label="节点类型">
          <span class="prop-readonly">{{ typeLabel }}</span>
        </PropertyField>

        <PropertyField label="描述">
          <textarea
            class="prop-textarea"
            :value="node.description ?? ''"
            @input="updateField('description', ($event.target as HTMLTextAreaElement).value)"
            rows="2"
            placeholder="添加节点描述..."
          ></textarea>
        </PropertyField>

        <PropertyField label="启用">
          <label class="prop-switch">
            <input
              type="checkbox"
              :checked="node.enabled"
              @change="updateField('enabled', ($event.target as HTMLInputElement).checked)"
            />
            <span class="switch-slider"></span>
          </label>
        </PropertyField>
      </PropertySection>

      <!-- 触发器配置 -->
      <PropertySection v-if="node.type === 'trigger'" title="触发器配置">
        <PropertyField label="触发方式">
          <select
            class="prop-select"
            :value="typedConfig.subType"
            @change="updateConfig('subType', ($event.target as HTMLSelectElement).value)"
          >
            <option value="manual">手动触发</option>
            <option value="webhook">Webhook</option>
            <option value="schedule">定时触发</option>
            <option value="event">事件触发</option>
          </select>
        </PropertyField>

        <template v-if="typedConfig.subType === 'webhook'">
          <PropertyField label="Webhook URL">
            <input
              class="prop-input"
              :value="typedConfig.webhookUrl ?? ''"
              @input="updateConfig('webhookUrl', ($event.target as HTMLInputElement).value)"
              placeholder="https://..."
            />
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'schedule'">
          <PropertyField label="Cron 表达式">
            <input
              class="prop-input"
              :value="typedConfig.cronExpression ?? ''"
              @input="updateConfig('cronExpression', ($event.target as HTMLInputElement).value)"
              placeholder="0 0 * * *"
            />
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'event'">
          <PropertyField label="事件名称">
            <input
              class="prop-input"
              :value="typedConfig.eventName ?? ''"
              @input="updateConfig('eventName', ($event.target as HTMLInputElement).value)"
              placeholder="order.created"
            />
          </PropertyField>
        </template>
      </PropertySection>

      <!-- 条件配置 -->
      <PropertySection v-if="node.type === 'condition'" title="条件配置">
        <div class="branches-list">
          <div
            v-for="(branch, idx) in typedConfig.branches ?? []"
            :key="idx"
            class="branch-item"
          >
            <div class="branch-header">
              <span class="branch-name">分支 {{ idx + 1 }}: {{ branch.name }}</span>
              <button class="btn-mini-remove" @click="removeBranch(idx)">✕</button>
            </div>
            <div
              v-for="(rule, rIdx) in branch.conditions"
              :key="rIdx"
              class="rule-row"
            >
              <input
                class="rule-input"
                :value="rule.field"
                @input="updateBranchRule(idx, rIdx, 'field', ($event.target as HTMLInputElement).value)"
                placeholder="字段"
              />
              <select
                class="rule-select"
                :value="rule.operator"
                @change="updateBranchRule(idx, rIdx, 'operator', ($event.target as HTMLSelectElement).value)"
              >
                <option value="equals">=</option>
                <option value="not_equals">≠</option>
                <option value="contains">包含</option>
                <option value="not_contains">不包含</option>
                <option value="greater_than">&gt;</option>
                <option value="less_than">&lt;</option>
                <option value="regex">正则</option>
                <option value="exists">存在</option>
                <option value="not_exists">不存在</option>
              </select>
              <input
                class="rule-input"
                :value="String(rule.value)"
                @input="updateBranchRule(idx, rIdx, 'value', ($event.target as HTMLInputElement).value)"
                placeholder="值"
              />
            </div>
            <button class="btn-add-rule" @click="addRule(idx)">+ 添加规则</button>
          </div>
          <button class="btn-add-branch" @click="addBranch">+ 添加分支</button>
        </div>
      </PropertySection>

      <!-- 动作配置 -->
      <PropertySection v-if="node.type === 'action'" title="动作配置">
        <PropertyField label="动作类型">
          <select
            class="prop-select"
            :value="typedConfig.subType"
            @change="updateConfig('subType', ($event.target as HTMLSelectElement).value)"
          >
            <option value="api_call">API 调用</option>
            <option value="notification">发送通知</option>
            <option value="transform">数据转换</option>
            <option value="script">执行脚本</option>
            <option value="delay">延迟等待</option>
          </select>
        </PropertyField>

        <template v-if="typedConfig.subType === 'api_call'">
          <PropertyField label="API URL">
            <input
              class="prop-input"
              :value="typedConfig.apiUrl ?? ''"
              @input="updateConfig('apiUrl', ($event.target as HTMLInputElement).value)"
              placeholder="https://api.example.com/..."
            />
          </PropertyField>
          <PropertyField label="HTTP 方法">
            <select
              class="prop-select"
              :value="typedConfig.apiMethod ?? 'POST'"
              @change="updateConfig('apiMethod', ($event.target as HTMLSelectElement).value)"
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
              <option value="PATCH">PATCH</option>
            </select>
          </PropertyField>
          <PropertyField label="请求体">
            <textarea
              class="prop-textarea"
              :value="typedConfig.apiBody ?? ''"
              @input="updateConfig('apiBody', ($event.target as HTMLTextAreaElement).value)"
              rows="4"
              placeholder='{"key": "value"}'
            ></textarea>
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'notification'">
          <PropertyField label="通知消息">
            <textarea
              class="prop-textarea"
              :value="typedConfig.notificationMessage ?? ''"
              @input="updateConfig('notificationMessage', ($event.target as HTMLTextAreaElement).value)"
              rows="3"
              placeholder="输入通知消息..."
            ></textarea>
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'transform'">
          <PropertyField label="转换脚本">
            <textarea
              class="prop-textarea"
              :value="typedConfig.transformScript ?? ''"
              @input="updateConfig('transformScript', ($event.target as HTMLTextAreaElement).value)"
              rows="4"
              placeholder="JavaScript 转换代码..."
            ></textarea>
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'script'">
          <PropertyField label="脚本">
            <textarea
              class="prop-textarea"
              :value="typedConfig.script ?? ''"
              @input="updateConfig('script', ($event.target as HTMLTextAreaElement).value)"
              rows="6"
              placeholder="自定义脚本..."
            ></textarea>
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'delay'">
          <PropertyField label="延迟(毫秒)">
            <input
              class="prop-input"
              type="number"
              :value="typedConfig.delayMs ?? 1000"
              @input="updateConfig('delayMs', Number(($event.target as HTMLInputElement).value))"
              placeholder="1000"
            />
          </PropertyField>
        </template>
      </PropertySection>

      <!-- 循环配置 -->
      <PropertySection v-if="node.type === 'loop'" title="循环配置">
        <PropertyField label="循环类型">
          <select
            class="prop-select"
            :value="typedConfig.subType"
            @change="updateConfig('subType', ($event.target as HTMLSelectElement).value)"
          >
            <option value="for_each">遍历循环</option>
            <option value="while">条件循环</option>
            <option value="repeat">重复次数</option>
          </select>
        </PropertyField>

        <template v-if="typedConfig.subType === 'for_each'">
          <PropertyField label="迭代变量名">
            <input
              class="prop-input"
              :value="typedConfig.iteratorVar ?? 'item'"
              @input="updateConfig('iteratorVar', ($event.target as HTMLInputElement).value)"
            />
          </PropertyField>
          <PropertyField label="数据源">
            <input
              class="prop-input"
              :value="typedConfig.collectionRef ?? ''"
              @input="updateConfig('collectionRef', ($event.target as HTMLInputElement).value)"
              placeholder="变量名或路径"
            />
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'while'">
          <PropertyField label="条件表达式">
            <input
              class="prop-input"
              :value="typedConfig.conditionExpression ?? ''"
              @input="updateConfig('conditionExpression', ($event.target as HTMLInputElement).value)"
              placeholder="变量名..."
            />
          </PropertyField>
        </template>

        <template v-if="typedConfig.subType === 'repeat'">
          <PropertyField label="重复次数">
            <input
              class="prop-input"
              type="number"
              :value="typedConfig.repeatCount ?? 5"
              @input="updateConfig('repeatCount', Number(($event.target as HTMLInputElement).value))"
              min="1"
            />
          </PropertyField>
        </template>

        <PropertyField label="最大迭代">
          <input
            class="prop-input"
            type="number"
            :value="typedConfig.maxIterations ?? 100"
            @input="updateConfig('maxIterations', Number(($event.target as HTMLInputElement).value))"
            min="1"
          />
        </PropertyField>
      </PropertySection>

      <!-- 删除按钮 -->
      <div class="property-actions">
        <button class="btn-delete" @click="$emit('delete')">
          🗑 删除节点
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { WorkflowNode, Workflow } from '../types';
import PropertySection from './PropertySection.vue';
import PropertyField from './PropertyField.vue';

const props = defineProps<{
  node: WorkflowNode;
  workflow: Workflow | null;
}>();

const emit = defineEmits<{
  'update:node': [nodeId: string, updates: Partial<WorkflowNode>];
  delete: [];
}>();

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    trigger: '触发器',
    condition: '条件',
    action: '动作',
    loop: '循环',
  };
  return labels[props.node.type] ?? props.node.type;
});

// 类型化的 config
const typedConfig = computed(() => props.node.config as Record<string, unknown>);

function updateField<K extends keyof WorkflowNode>(field: K, value: WorkflowNode[K]) {
  emit('update:node', props.node.id, { [field]: value });
}

function updateConfig(key: string, value: unknown) {
  const newConfig = { ...props.node.config, [key]: value };
  emit('update:node', props.node.id, { config: newConfig as WorkflowNode['config'] });
}

// ───── 条件分支操作 ─────
function addBranch() {
  const config = props.node.config as Record<string, unknown>;
  const branches = [...((config.branches as unknown[]) ?? [])];
  branches.push({
    name: `branch_${branches.length + 1}`,
    conditions: [],
    logic: 'and',
  });
  updateConfig('branches', branches);
}

function removeBranch(idx: number) {
  const config = props.node.config as Record<string, unknown>;
  const branches = [...((config.branches as unknown[]) ?? [])];
  branches.splice(idx, 1);
  updateConfig('branches', branches);
}

function addRule(branchIdx: number) {
  const config = props.node.config as Record<string, unknown>;
  const branches = JSON.parse(JSON.stringify((config.branches as unknown[]) ?? []));
  branches[branchIdx].conditions.push({
    field: '',
    operator: 'equals',
    value: '',
  });
  updateConfig('branches', branches);
}

function updateBranchRule(branchIdx: number, ruleIdx: number, key: string, value: unknown) {
  const config = props.node.config as Record<string, unknown>;
  const branches = JSON.parse(JSON.stringify((config.branches as unknown[]) ?? []));
  branches[branchIdx].conditions[ruleIdx][key] = value;
  updateConfig('branches', branches);
}
</script>

<style scoped>
.node-property-editor {
  height: 100%;
}

.property-content {
  padding: 12px 16px;
}

.property-actions {
  padding: 16px 0;
}

/* ───── 表单控件 ───── */
.prop-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
  background: var(--el-bg-color, #fff);
  box-sizing: border-box;
}
.prop-input:focus {
  outline: none;
  border-color: var(--el-color-primary, #409eff);
}

.prop-select {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
  background: var(--el-bg-color, #fff);
  cursor: pointer;
}

.prop-textarea {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  font-size: 12px;
  color: var(--el-text-color-primary, #303133);
  background: var(--el-bg-color, #fff);
  resize: vertical;
  font-family: 'Consolas', 'Monaco', monospace;
  box-sizing: border-box;
}
.prop-textarea:focus {
  outline: none;
  border-color: var(--el-color-primary, #409eff);
}

.prop-readonly {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
  font-family: monospace;
}

/* ───── 开关 ───── */
.prop-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 20px;
  cursor: pointer;
}

.prop-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.switch-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--el-border-color, #dcdfe6);
  border-radius: 10px;
  transition: 0.2s;
}

.switch-slider::before {
  content: '';
  position: absolute;
  height: 14px;
  width: 14px;
  left: 3px;
  bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}

.prop-switch input:checked + .switch-slider {
  background: var(--el-color-primary, #409eff);
}

.prop-switch input:checked + .switch-slider::before {
  transform: translateX(20px);
}

/* ───── 分支/规则编辑器 ───── */
.branches-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.branch-item {
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 6px;
  padding: 8px;
}

.branch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.branch-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular, #606266);
}

.btn-mini-remove {
  background: none;
  border: none;
  font-size: 12px;
  cursor: pointer;
  color: var(--el-text-color-placeholder, #c0c4cc);
  padding: 2px 4px;
}
.btn-mini-remove:hover {
  color: var(--el-color-danger, #f56c6c);
}

.rule-row {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.rule-input {
  flex: 1;
  padding: 4px 6px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 3px;
  font-size: 11px;
  min-width: 0;
}
.rule-input:focus {
  outline: none;
  border-color: var(--el-color-primary, #409eff);
}

.rule-select {
  width: 60px;
  padding: 4px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 3px;
  font-size: 11px;
}

.btn-add-rule,
.btn-add-branch {
  width: 100%;
  padding: 4px;
  margin-top: 4px;
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  border: 1px dashed var(--el-color-primary-light-5, #a0cfff);
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-add-rule:hover,
.btn-add-branch:hover {
  background: var(--el-color-primary-light-8, #d9ecff);
}

/* ───── 删除按钮 ───── */
.btn-delete {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--el-color-danger-light-5, #fab6b6);
  background: var(--el-color-danger-light-9, #fef0f0);
  color: var(--el-color-danger, #f56c6c);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-delete:hover {
  background: var(--el-color-danger, #f56c6c);
  color: #fff;
}
</style>
