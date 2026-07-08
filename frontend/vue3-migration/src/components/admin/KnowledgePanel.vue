<template>
  <div class="knowledge-panel">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ $t('admin.knowledge.title') }}</span>
          <el-button type="primary" size="small" @click="showUpload = true">
            <el-icon><Upload /></el-icon> {{ $t('admin.knowledge.uploadDoc') }}
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="documents">
        <el-table-column prop="name" :label="$t('admin.knowledge.docName')" min-width="200" />
        <el-table-column prop="type" :label="$t('admin.knowledge.docType')" width="100" />
        <el-table-column :label="$t('admin.knowledge.docSize')" width="120">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="chunks" :label="$t('admin.knowledge.chunks')" width="100" />
        <el-table-column prop="status" :label="$t('admin.knowledge.docStatus')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'indexed' ? 'success' : 'warning'">
              {{
                row.status === 'indexed'
                  ? $t('admin.knowledge.indexed')
                  : $t('admin.knowledge.processing')
              }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('admin.knowledge.docUploadTime')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('admin.knowledge.docActions')" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="reindex(row)">{{
              $t('admin.knowledge.reindex')
            }}</el-button>
            <el-button size="small" type="danger" @click="deleteDocument(row)">{{
              $t('admin.knowledge.delete')
            }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showUpload" :title="$t('admin.knowledge.uploadDoc')" width="500px">
      <FileUpload @success="handleUploadSuccess" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import apiClient from '@/api';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Upload } from '@element-plus/icons-vue';
import { formatSize, formatDate } from '@/utils/helpers';
import FileUpload from '@/components/files/FileUpload.vue';

interface Document {
  id: string;
  name: string;
  type: string;
  size: number;
  chunks: number;
  status: 'indexed' | 'processing';
  created: string;
}

const documents = ref<Document[]>([]);
const loading = ref<boolean>(false);
const showUpload = ref<boolean>(false);

onMounted(async () => {
  await fetchDocuments();
});

async function fetchDocuments(): Promise<void> {
  loading.value = true;
  try {
    const data = (await apiClient.get('/api/admin/documents')) as { documents?: Document[] };
    documents.value = data.documents || [];
  } catch (error) {
    console.error('获取文档列表失败:', error);
    ElMessage.error('获取文档列表失败');
  } finally {
    loading.value = false;
  }
}

async function reindex(document: Document): Promise<void> {
  try {
    await apiClient.post(`/api/admin/documents/${document.id}/reindex`);
    ElMessage.success('重建索引已启动');
    await fetchDocuments();
  } catch {
    ElMessage.error('重建索引失败');
  }
}

async function deleteDocument(document: Document): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要删除该文档吗？', '确认');
    await apiClient.delete(`/api/admin/documents/${document.id}`);
    ElMessage.success('文档删除成功');
    await fetchDocuments();
  } catch (error) {
    if (error instanceof Error) {
      ElMessage.error('删除失败: ' + error.message);
    }
  }
}

function handleUploadSuccess(): void {
  showUpload.value = false;
  fetchDocuments();
}
</script>

<style scoped lang="scss">
.knowledge-panel {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
