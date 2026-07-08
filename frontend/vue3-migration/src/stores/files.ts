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
} from '@/api/files';
import type { FileInfo } from '@/types';

export const useFileStore = defineStore('files', () => {
  // P0-4: 大数组改用 shallowRef
  const files = shallowRef<FileInfo[]>([]);
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);
  const total = ref<number>(0);

  // 搜索和筛选
  const searchQuery = ref<string>('');
  const typeFilter = ref<string>('');
  const currentPage = ref<number>(1);
  const pageSize = ref<number>(20);

  async function fetchFiles(): Promise<FileInfo[]> {
    loading.value = true;
    error.value = null;

    try {
      const params: Record<string, unknown> = {
        page: currentPage.value,
        page_size: pageSize.value,
      };
      if (searchQuery.value) params.q = searchQuery.value;
      if (typeFilter.value) params.type = typeFilter.value;

      const data = (await apiFetchFiles(params)) as {
        files: FileInfo[];
        total: number;
      };
      files.value = data.files || [];
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

  function getPreviewUrl(file: FileInfo): string {
    const hash = file.hash || file.id;
    return `/api/view/${hash}`;
  }

  function getDownloadUrl(file: FileInfo): string {
    const hash = file.hash || file.id;
    return `/api/download/${hash}`;
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

  // ============================
  // Mock 数据
  // ============================

  const MOCK_FILES: FileInfo[] = [
    {
      id: 'f-1',
      filename: '伏羲系统技术白皮书_v2.0.pdf',
      size: 2458624,
      uploadedAt: new Date(Date.now() - 86400000 * 2).toISOString(),
      type: 'pdf',
      hash: 'a1b2c3',
      status: 'ready',
    },
    {
      id: 'f-2',
      filename: 'RAG检索增强生成综述.docx',
      size: 1572864,
      uploadedAt: new Date(Date.now() - 86400000 * 5).toISOString(),
      type: 'docx',
      hash: 'd4e5f6',
      status: 'ready',
    },
    {
      id: 'f-3',
      filename: '2024年Q3数据报表.xlsx',
      size: 3145728,
      uploadedAt: new Date(Date.now() - 86400000 * 1).toISOString(),
      type: 'xlsx',
      hash: 'g7h8i9',
      status: 'processing',
    },
    {
      id: 'f-4',
      filename: '系统架构设计图.png',
      size: 524288,
      uploadedAt: new Date(Date.now() - 86400000 * 10).toISOString(),
      type: 'png',
      hash: 'j0k1l2',
      status: 'ready',
    },
    {
      id: 'f-5',
      filename: 'API接口文档.md',
      size: 128000,
      uploadedAt: new Date(Date.now() - 86400000 * 3).toISOString(),
      type: 'md',
      hash: 'm3n4o5',
      status: 'ready',
    },
    {
      id: 'f-6',
      filename: '用户手册v1.3.pdf',
      size: 5242880,
      uploadedAt: new Date(Date.now() - 86400000 * 15).toISOString(),
      type: 'pdf',
      hash: 'p6q7r8',
      status: 'uploaded',
    },
  ];

  function loadMockData(): FileInfo[] {
    let result = [...MOCK_FILES];

    // 搜索筛选
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase();
      result = result.filter((f) => f.filename.toLowerCase().includes(q));
    }

    // 类型筛选
    if (typeFilter.value) {
      result = result.filter((f) => f.filename.endsWith(`.${typeFilter.value}`));
    }

    total.value = result.length;
    const start = (currentPage.value - 1) * pageSize.value;
    files.value = result.slice(start, start + pageSize.value);
    return files.value;
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
    loadMockData,
  };
});
