# 示例插件

这是一个示例插件，用于演示伏羲系统的插件系统功能。

## 功能

- 提供示例 API 接口
- 演示插件生命周期事件

## API 接口

### GET /api/plugins/example/hello

返回问候语。

**响应示例**:
`json
{
  "success": true,
  "message": "你好！这是示例插件的接口",
  "data": {
    "plugin": "example-plugin",
    "version": "1.0.0",
    "timestamp": "2026-07-31"
  }
}
`

## 安装

1. 将插件目录复制到 plugins/installed/
2. 调用插件管理 API 安装插件
3. 激活插件

## 开发

参考本插件开发自己的插件。
