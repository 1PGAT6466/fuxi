<template>
  <div class="files-container">
    <div class="files-header">
      <h2>{{ $t('files.title') }}</h2>
      <el-button type="primary" @click="showUpload = true">
        <el-icon><Upload /></el-icon>
        {{ $t('files.uploadFile') }}
      </el-button>
    </div>

    <el-table v-loading="fileStore.loading" :data="fileStore.files">
      <el-table-column prop="name" :label="$t('files.fileName')" min-width="200" />
      <el-table-column prop="type" :label="$t('files.type')" width="100" />
      <el-table-column :label="$t('files.size')" width="120">
        <template #default="{ row }">
          {{ formatSize(row.size) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('files.uploadTime')" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created) }}
        </template>
      </el-table-column>
      <el-table-column :label="$t('files.actions')" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleDownload(row)">
            <el-icon><Download /></el-icon> {{ $t('files.download') }}
          </el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">
            <el-icon><Delete /></el-icon> {{ $t('files.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showUpload" :title="$t('files.upload')" width="500px">
      <FileUpload @success="handleUploadSuccess" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useFileStore } from '@/stores/files';
import { ElMessageBox, ElMessage } from 'element-plus';
import { Upload, Download, Delete } from '@element-plus/icons-vue';
import { formatSize, formatDate } from '@/utils/helpers';
import FileUpload from '@/components/files/FileUpload.vue';
import type { FileInfo } from '@/types';

const fileStore = useFileStore();
const showUpload = ref<boolean>(false);

onMounted(() => {
  fileStore.fetchFiles();
});

function handleDownload(file: FileInfo): void {
  // 使用当前源构造下载链接，兼容代理和不同部署环境
  const downloadUrl = `/api/files/${file.id}/download`;
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.click();
}

async function handleDelete(file: FileInfo): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要删除该文件吗？', '确认');
    await fileStore.deleteFile(file.id);
    ElMessage.success('文件删除成功');
  } catch (error) {
    if (error instanceof Error) {
      ElMessage.error('删除失败: ' + error.message);
    }
  }
}

function handleUploadSuccess(): void {
  showUpload.value = false;
  fileStore.fetchFiles();
  ElMessage.success('文件上传成功');
}

// 暴露给测试的内部状态和方法
defineExpose({
  fileStore,
  showUpload,
  handleDelete,
  handleDownload,
  handleUploadSuccess,
});
</script>

<style scoped lang="scss">
.files-container {
  padding: 20px;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    font-size: 20px;
    color: var(--text-primary);
  }
}
</style>
