"""Multi-View Splitter: Auto-detect and split multi-view reference images into panels.

Supports 3-view, 1+3, 2x2 layouts with automatic detection and manual coordinates.
"""

from __future__ import annotations

import json

import cv2
import numpy as np
import torch
from PIL import Image


# ---------------------------------------------------------------------------
# Multi-view layout detection
# ---------------------------------------------------------------------------

def _detect_layout(image_np):
    """Auto-detect multi-view layout. Returns (layout_type, panel_coords).

    Detects multiple layouts by analyzing pixel variance:
    - 3-view: 3 equal panels (front/side/back views)
    - 1+3 layout: left face close-up + right 3 views
    - 2x2 layout: four equal quadrants
    """
    h, w = image_np.shape[:2]
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    col_var = np.var(gray, axis=0)
    row_var = np.var(gray, axis=1)

    kernel_size = max(1, w // 100)
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = np.ones(kernel_size) / kernel_size

    # Check for horizontal split first (2x2 detection)
    mid_row_start = int(h * 0.3)
    mid_row_end = int(h * 0.7)
    row_var_smooth = np.convolve(row_var[mid_row_start:mid_row_end], kernel, mode="same")
    row_valleys = np.where(row_var_smooth < np.percentile(row_var_smooth, 30))[0]
    has_h_split = len(row_valleys) > 0

    # Find all vertical splits across full image width
    col_var_smooth = np.convolve(col_var, kernel, mode="same")
    threshold = np.percentile(col_var_smooth, 25)
    valleys = np.where(col_var_smooth < threshold)[0]

    # Group valleys into split positions
    split_positions = []
    if len(valleys) > 0:
        groups = []
        cg = [valleys[0]]
        for v in valleys[1:]:
            if v - cg[-1] <= kernel_size * 2:
                cg.append(v)
            else:
                groups.append(cg)
                cg = [v]
        groups.append(cg)
        split_positions = [int(np.mean(g)) for g in groups]

    # Detect 3-view layout: 2 vertical splits dividing image into 3 roughly equal parts
    if not has_h_split and len(split_positions) >= 2:
        third_w = w / 3
        for i in range(len(split_positions) - 1):
            s1, s2 = split_positions[i], split_positions[i + 1]
            if abs(s1 - third_w) < third_w * 0.3 and abs(s2 - third_w * 2) < third_w * 0.3:
                panels = [
                    (0, 0, s1, h),
                    (s1, 0, s2 - s1, h),
                    (s2, 0, w - s2, h),
                ]
                return "3-view", panels

    # Check for 1+3 layout: main split with left panel larger
    mid_start = int(w * 0.2)
    mid_end = int(w * 0.6)
    col_var_mid = np.convolve(col_var[mid_start:mid_end], kernel, mode="same")
    valleys_mid = np.where(col_var_mid < np.percentile(col_var_mid, 30))[0]

    main_split = None
    if len(valleys_mid) > 0:
        groups = []
        cg = [valleys_mid[0]]
        for v in valleys_mid[1:]:
            if v - cg[-1] <= kernel_size * 2:
                cg.append(v)
            else:
                groups.append(cg)
                cg = [v]
        groups.append(cg)
        best = max(groups, key=lambda g: len(g))
        main_split = mid_start + int(np.mean(best))

    if main_split is not None and not has_h_split:
        right_portion = gray[:, main_split:]
        right_col_smooth = np.convolve(np.var(right_portion, axis=0), kernel, mode="same")
        right_valleys = np.where(right_col_smooth < np.percentile(right_col_smooth, 30))[0]

        right_splits = 0
        if len(right_valleys) > 0:
            rg = []
            cg = [right_valleys[0]]
            for v in right_valleys[1:]:
                if v - cg[-1] <= kernel_size * 2:
                    cg.append(v)
                else:
                    rg.append(cg)
                    cg = [v]
            rg.append(cg)
            right_splits = len(rg)

        if right_splits >= 1:
            rw = w - main_split
            pw = rw // 3
            panels = [
                (0, 0, main_split, h),
                (main_split, 0, pw, h),
                (main_split + pw, 0, pw, h),
                (main_split + pw * 2, 0, rw - pw * 2, h),
            ]
            return "1+3", panels

    if has_h_split:
        rg = []
        cg = [row_valleys[0]]
        for v in row_valleys[1:]:
            if v - cg[-1] <= kernel_size * 2:
                cg.append(v)
            else:
                rg.append(cg)
                cg = [v]
        rg.append(cg)
        best = max(rg, key=lambda g: len(g))
        mrs = mid_row_start + int(np.mean(best))
        hw = w // 2
        bh = h - mrs
        panels = [
            (0, 0, hw, mrs),
            (hw, 0, w - hw, mrs),
            (0, mrs, hw, bh),
            (hw, mrs, w - hw, bh),
        ]
        return "2x2", panels

    # Fallback: check aspect ratio for likely 3-view (wide images)
    aspect_ratio = w / h
    if aspect_ratio >= 2.5:
        tw = w // 3
        panels = [
            (0, 0, tw, h),
            (tw, 0, tw, h),
            (tw * 2, 0, w - tw * 2, h),
        ]
        return "3-view", panels

    # Default fallback: equal quarters (1+3)
    tw = w // 4
    panels = [
        (0, 0, tw, h),
        (tw, 0, tw, h),
        (tw * 2, 0, tw, h),
        (tw * 3, 0, w - tw * 3, h),
    ]
    return "1+3", panels


def _split_panels(image, layout_mode, panel_coords=None):
    """Split IMAGE tensor into panels based on layout mode."""
    img = image[0] if image.ndim == 4 else image
    img_np = (img.cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
    h, w = img_np.shape[:2]

    # Priority: custom coords > layout mode defaults
    if panel_coords:
        coords = panel_coords
    elif layout_mode == "2-view":
        # 2 equal horizontal panels
        pw = w // 2
        coords = [
            (0, 0, pw, h),
            (pw, 0, w - pw, h),
        ]
    elif layout_mode == "3-view":
        pw = w // 3
        coords = [
            (0, 0, pw, h),
            (pw, 0, pw, h),
            (pw * 2, 0, w - pw * 2, h),
        ]
    elif layout_mode == "1+3":
        main_split = w // 2
        rw = w - main_split
        pw = rw // 3
        coords = [
            (0, 0, main_split, h),
            (main_split, 0, pw, h),
            (main_split + pw, 0, pw, h),
            (main_split + pw * 2, 0, rw - pw * 2, h),
        ]
    elif layout_mode == "2x2":
        hw = w // 2
        hh = h // 2
        coords = [
            (0, 0, hw, hh),
            (hw, 0, w - hw, hh),
            (0, hh, hw, h - hh),
            (hw, hh, w - hw, h - hh),
        ]
    elif layout_mode == "3x3":
        cw = w // 3
        ch = h // 3
        coords = []
        for row in range(3):
            for col in range(3):
                px = col * cw
                py = row * ch
                pw = cw if col < 2 else w - px
                ph = ch if row < 2 else h - py
                coords.append((px, py, pw, ph))
    elif layout_mode == "6x6":
        cw = w // 6
        ch = h // 6
        coords = []
        for row in range(6):
            for col in range(6):
                px = col * cw
                py = row * ch
                pw = cw if col < 5 else w - px
                ph = ch if row < 5 else h - py
                coords.append((px, py, pw, ph))
    else:
        _, coords = _detect_layout(img_np)

    panels = []
    for (x, y, pw, ph) in coords:
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(w, int(x + pw)), min(h, int(y + ph))
        panel_np = img_np[y1:y2, x1:x2]
        panels.append(torch.from_numpy(panel_np.astype(np.float32) / 255.0))
    return panels


# ---------------------------------------------------------------------------
# Node: MultiViewSplitter
# ---------------------------------------------------------------------------

class MultiViewSplitter:
    """Auto-detect and split multi-view reference images into panels.

    Supports multiple layouts:
    - 3-view: 3 equal panels (front/side/back views)
    - 1+3 layout: left face close-up + right 3 views
    - 2x2 layout: four equal quadrants
    - manual: custom panel coordinates via JSON string
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "layout_mode": (["2-view", "3-view", "1+3", "2x2", "3x3", "6x6", "manual"], {"default": "1+3"}),
                "panel_index": ("INT", {"default": -1, "min": -1, "max": 10, "step": 1,
                                        "tooltip": "-1 = all panels, 0 = first panel, 1 = second panel, etc."}),
            },
            "optional": {
                "panel_coords": ("STRING", {"default": "", "multiline": True}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("panels", "panel_count")
    FUNCTION = "split"
    CATEGORY = "MultiViewSplitter"
    OUTPUT_IS_LIST = (True, False)

    def split(self, image, layout_mode, panel_index=-1, panel_coords="", unique_id=None):
        coords = json.loads(panel_coords) if panel_coords.strip() else None
        panels = _split_panels(image, layout_mode, coords)
        if panel_index >= 0 and panel_index < len(panels):
            panels = [panels[panel_index]]
        panels = [p.unsqueeze(0) if p.ndim == 3 else p for p in panels]

        # Send image dimensions to frontend via send_sync
        try:
            import server
            img_for_cache = image[0] if image.ndim == 4 else image
            h, w = img_for_cache.shape[0], img_for_cache.shape[1]
            server.PromptServer.instance.send_sync(
                "local_reference_image_size",
                {"node_id": unique_id, "width": w, "height": h},
            )
        except Exception:
            pass

        return (panels, len(panels))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

NODE_CLASS_MAPPINGS = {
    "MultiViewSplitter": MultiViewSplitter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiViewSplitter": "Multi-View Splitter",
}
