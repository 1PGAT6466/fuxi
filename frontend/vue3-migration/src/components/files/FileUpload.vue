<template>
  <div class="file-upload">
    <el-upload
      ref="uploadRef"
      :auto-upload="false"
      :on-change="handleFileChange"
      :file-list="fileList"
      :limit="5"
      :on-exceed="handleExceed"
      drag
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">
        {{ $t('upload.dragText') }}<em>{{ $t('upload.clickUpload') }}</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          {{ $t('upload.tip') }}
        </div>
      </template>
    </el-upload>

    <div class="upload-actions">
      <el-button @click="handleCancel">{{ $t('upload.cancel') }}</el-button>
      <el-button type="primary" :loading="uploading" @click="handleUpload">
        {{ $t('upload.startUpload') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { UploadFilled } from '@element-plus/icons-vue';
import { useFileStore } from '@/stores/files';
import { ElMessage } from 'element-plus';
import type { UploadInstance, UploadFile } from 'element-plus';

const emit = defineEmits<{
  success: [];
}>();

const fileStore = useFileStore();
const uploadRef = ref<UploadInstance>();
const fileList = ref<UploadFile[]>([]);
const uploading = ref<boolean>(false);

function handleFileChange(_file: UploadFile, files: UploadFile[]): void {
  fileList.value = files;
}

function handleExceed(): void {
  ElMessage.warning('最多只能上传5个文件');
}

function handleCancel(): void {
  fileList.value = [];
  uploadRef.value?.clearFiles();
}

async function handleUpload(): Promise<void> {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件');
    return;
  }

  uploading.value = true;

  try {
    for (const file of fileList.value) {
      await fileStore.uploadFile(file.raw as File);
    }

    ElMessage.success('文件上传成功');
    emit('success');
    handleCancel();
  } catch (error) {
    ElMessage.error('上传失败: ' + ((error as Error)?.message || '未知错误'));
  } finally {
    uploading.value = false;
  }
}

// 暴露给测试的内部状态和方法
defineExpose({
  fileList,
  uploading,
  uploadRef,
  handleUpload,
  handleFileChange,
  handleCancel,
  handleExceed,
});
</script>

<style scoped lang="scss">
.file-upload {
  padding: 20px;
}

.upload-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
