/**
 * 伏羲 v2.1 — Files Store
 * 文件列表 + 上传/下载/删除/搜索/分页
 */
import { defineStore } from 'pinia';
import { ref, shallowRef } from 'vue';
import {
  fetchFiles as apiFetchFiles,
  uploadFile as apiUploadFile,
  deleteFile as apiDeleteFile,
  type BackendFileInfo,
} from '@/api/files';

export interface DisplayFileInfo {
  id: string;
  filename: string;
  size: number;
  type: string;
  uploadedAt: string;
  hash: string;
  status: 'ready' | 'processing' | 'uploaded';
  chunkCount: number;
}

function backendToDisplay(f: BackendFileInfo): DisplayFileInfo {
  const ext = f.file_name.split('.').pop() || 'unknown';
  return {
    id: f.file_hash,
    filename: f.file_name,
    size: 0, // 后端暂不返回 size
    type: ext,
    uploadedAt: new Date().toISOString(), // 后端暂不返回时间
    hash: f.file_hash,
    status: 'ready',
    chunkCount: f.chunk_count,
  };
}

export const useFileStore = defineStore('files', () => {
  const files = shallowRef<DisplayFileInfo[]>([]);
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);
  const total = ref<number>(0);

  const searchQuery = ref<string>('');
  const typeFilter = ref<string>('');
  const currentPage = ref<number>(1);
  const pageSize = ref<number>(20);

  async function fetchFiles(): Promise<DisplayFileInfo[]> {
    loading.value = true;
    error.value = null;

    try {
      const params: Record<string, unknown> = {
        page: currentPage.value,
        page_size: pageSize.value,
      };
      if (searchQuery.value) params.q = searchQuery.value;

      const data = await apiFetchFiles(params);
      files.value = (data.files || []).map(backendToDisplay);
      total.value = data.total || 0;
      return files.value;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取文件列表失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function uploadFile(file: File): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);

    await apiUploadFile(formData);
  }

  async function deleteFile(fileId: string): Promise<void> {
    await apiDeleteFile(fileId);
    files.value = files.value.filter((f) => f.id !== fileId);
  }

  function getPreviewUrl(file: DisplayFileInfo): string {
    return `/api/view/${file.hash}`;
  }

  function getDownloadUrl(file: DisplayFileInfo): string {
    return `/api/download/${file.hash}`;
  }

  function setSearch(query: string): void {
    searchQuery.value = query;
    currentPage.value = 1;
  }

  function setTypeFilter(type: string): void {
    typeFilter.value = type;
    currentPage.value = 1;
  }

  function setPage(page: number): void {
    currentPage.value = page;
  }

  return {
    files,
    loading,
    error,
    total,
    searchQuery,
    typeFilter,
    currentPage,
    pageSize,
    fetchFiles,
    uploadFile,
    deleteFile,
    getPreviewUrl,
    getDownloadUrl,
    setSearch,
    setTypeFilter,
    setPage,
  };
});
