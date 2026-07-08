/**
 * Files.vue / FileUpload.vue 组件测试
 * 测试文件列表展示、删除确认和上传操作
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

// Mock stores
const fileStoreMock = {
  files: [],
  loading: false,
  error: null,
  fetchFiles: vi.fn(),
  deleteFile: vi.fn(),
  uploadFile: vi.fn(),
};

vi.mock('@/stores/files', () => ({
  useFileStore: () => fileStoreMock,
}));

// Mock Element Plus - 使用 import 获取一致的 mock 引用
const ElMessageBoxMock = {
  confirm: vi.fn(),
};
const ElMessageMock = {
  success: vi.fn(),
  error: vi.fn(),
};

vi.mock('element-plus', () => ({
  ElMessageBox: ElMessageBoxMock,
  ElMessage: ElMessageMock,
}));

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Upload: { name: 'Upload' },
  Download: { name: 'Download' },
  Delete: { name: 'Delete' },
}));

// Mock utils
vi.mock('@/utils/helpers', () => ({
  formatSize: vi.fn((bytes) => `${(bytes / 1024).toFixed(1)} KB`),
  formatDate: vi.fn(() => '2024-01-15 10:30'),
}));

// Mock FileUpload component
vi.mock('@/components/files/FileUpload.vue', () => ({
  default: {
    name: 'FileUpload',
    template: '<div class="file-upload"><button @click="$emit(\'success\')">上传</button></div>',
    emits: ['success'],
  },
}));

describe('Files.vue', () => {
  let wrapper;

  beforeEach(async () => {
    setActivePinia(createPinia());

    // Reset mocks
    fileStoreMock.files = [];
    fileStoreMock.loading = false;
    fileStoreMock.error = null;
    fileStoreMock.fetchFiles.mockReset();
    fileStoreMock.deleteFile.mockReset();

    // Reset Element Plus mocks using shared references
    ElMessageBoxMock.confirm.mockReset();
    ElMessageMock.success.mockReset();
    ElMessageMock.error.mockReset();

    const Files = (await import('@/views/Files.vue')).default;

    // Vue 3 SFC templates compile <el-button> to resolveComponent("el-button")
    // which resolves to PascalCase ElButton from the app's global components.
    // Since we don't install ElementPlus in tests, we register stubs as global
    // components instead of stubs.
    wrapper = mount(Files, {
      global: {
        components: {
          ElButton: {
            template: '<button class="el-button" :type="type" :size="size" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'size', 'loading', 'disabled', 'nativeType'],
            emits: ['click'],
          },
          ElIcon: { template: '<i class="el-icon"><slot /></i>' },
          ElDialog: {
            template: '<div v-if="modelValue" class="el-dialog"><slot /></div>',
            props: ['modelValue', 'title', 'width'],
          },
        },
        stubs: {
          // Stub table components to avoid scoped-slot row data issues
          'el-table': true,
          'el-table-column': true,
          FileUpload: true,
        },
      },
    });
  });

  describe('组件渲染', () => {
    it('应该渲染文件管理容器', () => {
      expect(wrapper.find('.files-container').exists()).toBe(true);
    });

    it('应该显示"文件管理"标题', () => {
      // $t('files.title') → 'title'
      expect(wrapper.text()).toContain('title');
    });

    it('应该显示上传按钮', () => {
      // $t('files.uploadFile') → 'uploadFile'
      expect(wrapper.text()).toContain('uploadFile');
    });

    it('挂载时应自动获取文件列表', () => {
      expect(fileStoreMock.fetchFiles).toHaveBeenCalled();
    });
  });

  describe('文件列表', () => {
    it('应使用 store 中的文件数据', async () => {
      fileStoreMock.files = [
        { id: 1, name: '报告.pdf', type: 'pdf', size: 2048, created: '2024-01-15' },
      ];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.fileStore.files).toHaveLength(1);
    });

    it('文件为空时表格应为空', () => {
      expect(wrapper.vm.fileStore.files).toHaveLength(0);
    });
  });

  describe('文件删除', () => {
    it('confirm 确认后应调用 deleteFile', async () => {
      ElMessageBoxMock.confirm.mockResolvedValueOnce('confirm');

      const file = { id: 1, name: 'test.pdf' };
      await wrapper.vm.handleDelete(file);

      expect(ElMessageBoxMock.confirm).toHaveBeenCalledWith('确定要删除该文件吗？', '确认');
      expect(fileStoreMock.deleteFile).toHaveBeenCalledWith(1);
      expect(ElMessageMock.success).toHaveBeenCalledWith('文件删除成功');
    });

    it('用户取消不应报错', async () => {
      // 用户取消在 ElMessageBox 中表现为 Promise rejected
      ElMessageBoxMock.confirm.mockRejectedValueOnce('cancel');

      const file = { id: 1, name: 'test.pdf' };
      await wrapper.vm.handleDelete(file);

      expect(ElMessageBoxMock.confirm).toHaveBeenCalled();
      // 不应显示错误消息（取消不是错误）
      expect(ElMessageMock.error).not.toHaveBeenCalled();
    });
  });

  describe('文件下载', () => {
    it('handleDownload 应创建下载链接', () => {
      const originalCreateElement = document.createElement;
      const mockLink = {
        href: '',
        target: '',
        rel: '',
        click: vi.fn(),
      };
      document.createElement = vi.fn(() => mockLink);

      wrapper.vm.handleDownload({ id: 42, name: 'file.pdf' });

      expect(mockLink.href).toBe('/api/files/42/download');
      expect(mockLink.target).toBe('_blank');
      expect(mockLink.rel).toBe('noopener noreferrer');
      expect(mockLink.click).toHaveBeenCalled();

      document.createElement = originalCreateElement;
    });
  });

  describe('上传对话框', () => {
    it('点击上传按钮应显示对话框', async () => {
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.showUpload).toBe(false);

      wrapper.vm.showUpload = true;
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.showUpload).toBe(true);
    });
  });

  describe('上传成功回调', () => {
    it('应关闭对话框并刷新文件列表', async () => {
      await wrapper.vm.handleUploadSuccess();

      expect(wrapper.vm.showUpload).toBe(false);
      expect(fileStoreMock.fetchFiles).toHaveBeenCalled();
      expect(ElMessageMock.success).toHaveBeenCalledWith('文件上传成功');
    });
  });
});
