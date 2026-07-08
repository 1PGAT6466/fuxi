/**
 * filesStore 测试
 * 测试文件列表获取、上传和删除
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

// Mock API client
const mockApiClient = {
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
};

vi.mock('@/api', () => ({
  default: mockApiClient,
}));

describe('filesStore', () => {
  let filesStore;

  beforeEach(async () => {
    setActivePinia(createPinia());
    mockApiClient.get.mockReset();
    mockApiClient.post.mockReset();
    mockApiClient.delete.mockReset();

    const { useFileStore } = await import('@/stores/files');
    filesStore = useFileStore();
  });

  describe('初始状态', () => {
    it('初始 files 为空数组', () => {
      expect(filesStore.files).toEqual([]);
    });

    it('初始 loading 为 false', () => {
      expect(filesStore.loading).toBe(false);
    });

    it('初始 error 为 null', () => {
      expect(filesStore.error).toBeNull();
    });
  });

  describe('fetchFiles', () => {
    it('应获取并设置文件列表', async () => {
      const mockFiles = [
        { id: 1, name: '文档.pdf', size: 1024000, type: 'pdf' },
        { id: 2, name: '图片.png', size: 512000, type: 'png' },
      ];
      mockApiClient.get.mockResolvedValueOnce({ files: mockFiles });

      const result = await filesStore.fetchFiles();

      expect(filesStore.files).toEqual(mockFiles);
      expect(result).toEqual(mockFiles);
    });

    it('应调用正确的 API', async () => {
      mockApiClient.get.mockResolvedValueOnce({ files: [] });

      await filesStore.fetchFiles();

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/files');
    });

    it('响应无 files 字段时应设为空数组', async () => {
      mockApiClient.get.mockResolvedValueOnce({});

      await filesStore.fetchFiles();

      expect(filesStore.files).toEqual([]);
    });

    it('API 失败时应抛出错误', async () => {
      const err = new Error('服务器错误');
      mockApiClient.get.mockRejectedValueOnce(err);

      await expect(filesStore.fetchFiles()).rejects.toThrow('服务器错误');
      expect(filesStore.error).toBe('服务器错误');
    });

    it('fetchFiles 后 loading 应恢复 false', async () => {
      mockApiClient.get.mockRejectedValueOnce(new Error('fail'));

      await filesStore.fetchFiles().catch(() => {});
      expect(filesStore.loading).toBe(false);
    });
  });

  describe('uploadFile', () => {
    it('应创建 FormData 并上传', async () => {
      mockApiClient.post.mockResolvedValueOnce({ id: 1 });
      mockApiClient.get.mockResolvedValueOnce({ files: [{ id: 1 }] });

      const mockFile = new File(['content'], 'test.pdf', { type: 'application/pdf' });

      const result = await filesStore.uploadFile(mockFile);

      expect(mockApiClient.post).toHaveBeenCalled();
      expect(result).toEqual({ id: 1 });
    });

    it('上传成功后应刷新文件列表', async () => {
      mockApiClient.post.mockResolvedValueOnce({ id: 2 });
      mockApiClient.get.mockResolvedValueOnce({
        files: [{ id: 1 }, { id: 2 }],
      });

      await filesStore.uploadFile(new File([], 'test.txt'));

      // fetchFiles 会被调用两次（uploadFile 内部 + post 后）
      expect(mockApiClient.get).toHaveBeenCalled();
    });

    it('上传失败时应设置 error', async () => {
      mockApiClient.post.mockRejectedValueOnce(new Error('文件太大'));

      await filesStore.uploadFile(new File([], 'big.zip')).catch(() => {});

      expect(filesStore.error).toBe('文件太大');
    });
  });

  describe('deleteFile', () => {
    it('应调用删除 API', async () => {
      mockApiClient.delete.mockResolvedValueOnce({});
      mockApiClient.get.mockResolvedValueOnce({ files: [] });

      await filesStore.deleteFile(42);

      expect(mockApiClient.delete).toHaveBeenCalledWith('/api/files/42');
    });

    it('删除后应刷新文件列表', async () => {
      mockApiClient.delete.mockResolvedValueOnce({});
      mockApiClient.get.mockResolvedValueOnce({
        files: [{ id: 2, name: 'remaining.txt' }],
      });

      await filesStore.deleteFile(1);

      expect(mockApiClient.get).toHaveBeenCalled();
      expect(filesStore.files).toHaveLength(1);
    });

    it('删除失败时应设置 error', async () => {
      mockApiClient.delete.mockRejectedValueOnce(new Error('权限不足'));

      await filesStore.deleteFile(1).catch(() => {});

      expect(filesStore.error).toBe('权限不足');
    });
  });
});
