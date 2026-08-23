# ComfyUI-Multi-View-Splitter

ComfyUI 自定义节点，用于将多视图参考图自动分割为独立面板，支持角色一致性工作流中的多视角参考图处理。

## 功能特性

- 支持多种布局模式：2-view、3-view、1+3、2x2、3x3、6x6、manual
- 自动检测布局（基于像素方差分析）
- 滑块 GUI 交互，可拖拽调节分割位置
- 自定义坐标 JSON 输入，精确控制分割
- 选择输出特定面板（panel_index）
- 输出为列表模式，兼容下游节点批量处理

## 布局模式

| 模式 | 说明 | 面板数 | 滑块 |
|------|------|--------|------|
| `2-view` | 2 等分横向面板 | 2 | 1 个 |
| `3-view` | 3 等分横向面板（正面/侧面/背面） | 3 | 2 个 |
| `1+3` | 左侧大图 + 右侧 3 小图 | 4 | 3 个 |
| `2x2` | 四等分网格 | 4 | 2 个 |
| `3x3` | 九宫格均匀分割 | 9 | 无 |
| `6x6` | 36 宫格均匀分割 | 36 | 无 |
| `manual` | 自定义 JSON 坐标 | 自定义 | 无 |

## 节点参数

### 必需参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `image` | IMAGE | - | 输入的多视图参考图 |
| `layout_mode` | Combo | `1+3` | 布局模式 |
| `panel_index` | INT | `-1` | 选择输出的面板编号（-1 = 全部） |

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `panel_coords` | STRING | `""` | 自定义面板坐标 JSON |

### 输出

| 输出 | 类型 | 说明 |
|------|------|------|
| `panels` | IMAGE (列表) | 分割后的面板图像 |
| `panel_count` | INT | 面板数量 |

## 滑块交互

选择 `2-view`、`3-view`、`1+3` 或 `2x2` 布局时，节点下方会出现滑块控件：

- **1+3 布局**：Main Split（主分割线）、Right 1（右侧第 1 条线）、Right 2（右侧第 2 条线）
- **3-view 布局**：Split 1、Split 2
- **2-view 布局**：Split 1
- **2x2 布局**：V Split（垂直）、H Split（水平）

拖动滑块时，`panel_coords` 会自动更新为对应的 JSON 坐标。最后一块面板的宽度/高度会自动计算为总尺寸减去前面所有分割的总和。

## 自定义坐标格式

`panel_coords` 使用 JSON 格式，每个面板为 `[x, y, width, height]`：

```json
[[0, 0, 1024, 1152], [1024, 0, 341, 1152], [1365, 0, 341, 1152], [1706, 0, 342, 1152]]
```

- `x, y`：面板左上角坐标（像素）
- `width, height`：面板宽度和高度（像素）

## 安装

将 `ComfyUI-Multi-View-Splitter` 文件夹放入 ComfyUI 的 `custom_nodes` 目录：

```
ComfyUI/
  custom_nodes/
    ComfyUI-Multi-View-Splitter/
      __init__.py
      nodes.py
      web/js/panel_splitter.js
```

重启 ComfyUI 即可在节点列表中看到 **Multi-View Splitter**。

## 依赖

- torch
- numpy
- Pillow
- opencv-python-headless

## 使用示例

1. 加载多视图参考图（如角色四视图）
2. 连接到 Multi-View Splitter 节点
3. 选择合适的 `layout_mode`（如 `1+3`）
4. 拖动滑块微调分割位置
5. 将 `panels` 输出连接到下游节点（如 Krea2 多帧参考注入）

