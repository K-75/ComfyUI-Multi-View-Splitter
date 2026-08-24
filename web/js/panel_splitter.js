import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

app.registerExtension({
  name: "LocalReference.PanelSplitter",

  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== "MultiViewSplitter") return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      const node = this;

      const coordsWidget = node.widgets?.find(w => w.name === "panel_coords");
      const layoutWidget = node.widgets?.find(w => w.name === "layout_mode");

      // Create slider container
      const sliderContainer = document.createElement("div");
      sliderContainer.style.cssText = "margin-top:8px; padding:4px 0;";

      const label = document.createElement("div");
      label.textContent = "Split Positions (pixels)";
      label.style.cssText = "font-size:11px; color:#aaa; margin-bottom:4px;";
      sliderContainer.appendChild(label);

      const infoLabel = document.createElement("div");
      infoLabel.textContent = "Image size: unknown";
      infoLabel.style.cssText = "font-size:10px; color:#666; margin-bottom:6px;";
      sliderContainer.appendChild(infoLabel);

      const slidersDiv = document.createElement("div");
      slidersDiv.style.cssText = "display:flex; flex-direction:column; gap:4px;";
      sliderContainer.appendChild(slidersDiv);

      const sliderWidget = node.addDOMWidget("split_sliders", "custom", sliderContainer, {
        serialize: false,
      });

      // Image dimensions
      let imgW = 2048, imgH = 1152;

      // Split positions in pixels
      let vPositions = [1024, 1536, 1920];
      let hPosition = 576;

      function createSlider(labelText, value, min, max, step, onChange) {
        const row = document.createElement("div");
        row.style.cssText = "display:flex; align-items:center; gap:6px;";

        const lbl = document.createElement("span");
        lbl.textContent = labelText;
        lbl.style.cssText = "font-size:11px; color:#ccc; min-width:70px;";

        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = min;
        slider.max = max;
        slider.step = step;
        slider.value = value;
        slider.style.cssText = "flex:1; height:4px; accent-color:#4a9eff;";

        const valLabel = document.createElement("span");
        valLabel.textContent = Math.round(value) + "px";
        valLabel.style.cssText = "font-size:10px; color:#888; min-width:50px; text-align:right;";

        slider.addEventListener("input", () => {
          const v = parseFloat(slider.value);
          valLabel.textContent = Math.round(v) + "px";
          onChange(v);
        });

        row.appendChild(lbl);
        row.appendChild(slider);
        row.appendChild(valLabel);
        return row;
      }

      function rebuildSliders() {
        slidersDiv.innerHTML = "";
        const layout = layoutWidget?.value || "manual";

        // Grid layouts (3x3, 6x6) and manual have no sliders
        if (layout === "3x3" || layout === "6x6" || layout === "manual") {
          const hint = document.createElement("div");
          hint.textContent = layout === "manual"
            ? "Enter panel coords as JSON below"
            : `Uniform ${layout} grid — use manual for custom splits`;
          hint.style.cssText = "font-size:11px; color:#666; font-style:italic;";
          slidersDiv.appendChild(hint);
          return;
        }

        if (layout === "2-view") {
          slidersDiv.appendChild(createSlider("Split", vPositions[0], 10, imgW - 10, 1, (v) => {
            vPositions[0] = v;
            updateCoords();
          }));
        } else if (layout === "2x2") {
          slidersDiv.appendChild(createSlider("V Split", vPositions[0], 10, imgW - 10, 1, (v) => {
            vPositions[0] = v;
            updateCoords();
          }));
          slidersDiv.appendChild(createSlider("H Split", hPosition, 10, imgH - 10, 1, (v) => {
            hPosition = v;
            updateCoords();
          }));
        } else if (layout === "3-view") {
          slidersDiv.appendChild(createSlider("Split 1", vPositions[0], 10, imgW * 0.5, 1, (v) => {
            vPositions[0] = v;
            if (vPositions[0] >= vPositions[1]) vPositions[1] = vPositions[0] + 10;
            updateCoords();
          }));
          slidersDiv.appendChild(createSlider("Split 2", vPositions[1], imgW * 0.4, imgW - 10, 1, (v) => {
            vPositions[1] = v;
            if (vPositions[1] <= vPositions[0]) vPositions[0] = vPositions[1] - 10;
            updateCoords();
          }));
        } else {
          // 1+3
          slidersDiv.appendChild(createSlider("Main Split", vPositions[0], imgW * 0.2, imgW * 0.7, 1, (v) => {
            vPositions[0] = v;
            updateCoords();
          }));
          slidersDiv.appendChild(createSlider("Right 1", vPositions[1], vPositions[0] + 10, imgW * 0.9, 1, (v) => {
            vPositions[1] = v;
            if (vPositions[1] <= vPositions[0]) vPositions[0] = vPositions[1] - 10;
            updateCoords();
          }));
          slidersDiv.appendChild(createSlider("Right 2", vPositions[2], vPositions[1] + 10, imgW - 1, 1, (v) => {
            vPositions[2] = v;
            if (vPositions[2] <= vPositions[1]) vPositions[1] = vPositions[2] - 10;
            updateCoords();
          }));
        }
      }

      function updateCoords() {
        if (!coordsWidget) return;
        const layout = layoutWidget?.value || "manual";
        let coords = [];

        if (layout === "2-view") {
          const x1 = Math.round(vPositions[0]);
          coords = [
            [0, 0, x1, imgH],
            [x1, 0, imgW - x1, imgH],
          ];
        } else if (layout === "2x2") {
          const vx = Math.round(vPositions[0]);
          const hy = Math.round(hPosition);
          coords = [
            [0, 0, vx, hy],
            [vx, 0, imgW - vx, hy],
            [0, hy, vx, imgH - hy],
            [vx, hy, imgW - vx, imgH - hy],
          ];
        } else if (layout === "3-view") {
          const x1 = Math.round(vPositions[0]);
          const x2 = Math.round(vPositions[1]);
          coords = [
            [0, 0, x1, imgH],
            [x1, 0, x2 - x1, imgH],
            [x2, 0, imgW - x2, imgH],
          ];
        } else if (layout === "1+3") {
          const x1 = Math.round(vPositions[0]);
          const x2 = Math.round(vPositions[1]);
          const x3 = Math.round(vPositions[2]);
          coords = [
            [0, 0, x1, imgH],
            [x1, 0, x2 - x1, imgH],
            [x2, 0, x3 - x2, imgH],
            [x3, 0, imgW - x3, imgH],
          ];
        } else if (layout === "3x3") {
          const cw = Math.round(imgW / 3), ch = Math.round(imgH / 3);
          for (let row = 0; row < 3; row++) {
            for (let col = 0; col < 3; col++) {
              const px = col * cw, py = row * ch;
              const pw = col < 2 ? cw : imgW - px;
              const ph = row < 2 ? ch : imgH - py;
              coords.push([px, py, pw, ph]);
            }
          }
        } else if (layout === "6x6") {
          const cw = Math.round(imgW / 6), ch = Math.round(imgH / 6);
          for (let row = 0; row < 6; row++) {
            for (let col = 0; col < 6; col++) {
              const px = col * cw, py = row * ch;
              const pw = col < 5 ? cw : imgW - px;
              const ph = row < 5 ? ch : imgH - py;
              coords.push([px, py, pw, ph]);
            }
          }
        }

        coordsWidget.value = JSON.stringify(coords);
      }

      // Parse existing coords to restore slider positions
      function parseExistingCoords() {
        const raw = coordsWidget?.value || "";
        if (!raw.trim()) return null;
        try {
          const coords = JSON.parse(raw);
          if (!Array.isArray(coords) || coords.length === 0) return null;
          return coords;
        } catch { return null; }
      }

      // Apply parsed coords to slider positions
      function applyCoordsToSliders(coords) {
        if (!coords) return false;
        const layout = layoutWidget?.value || "manual";

        if (layout === "2-view" && coords.length >= 2) {
          vPositions = [coords[1][0]];
          return true;
        } else if (layout === "2x2" && coords.length >= 2) {
          vPositions = [coords[1][0]];
          hPosition = coords[2][1];
          return true;
        } else if (layout === "3-view" && coords.length >= 3) {
          vPositions = [coords[1][0], coords[2][0]];
          return true;
        } else if (layout === "1+3" && coords.length >= 4) {
          vPositions = [coords[1][0], coords[2][0], coords[3][0]];
          return true;
        }
        return false;
      }

      // Listen for image size from backend via send_sync
      api.addEventListener("local_reference_image_size", (event) => {
        const data = event.detail;
        if (data.node_id !== node.id) return;

        imgW = data.width;
        imgH = data.height;
        infoLabel.textContent = `Image size: ${imgW} x ${imgH}`;

        // Priority: existing manual coords > defaults
        const existingCoords = parseExistingCoords();
        if (!applyCoordsToSliders(existingCoords)) {
          const layout = layoutWidget?.value || "manual";
          if (layout === "2-view") {
            vPositions = [imgW / 2];
          } else if (layout === "2x2") {
            vPositions = [imgW / 2];
            hPosition = imgH / 2;
          } else if (layout === "3-view") {
            vPositions = [imgW / 3, imgW * 2 / 3];
          } else {
            vPositions = [imgW / 2, imgW * 0.75, imgW * 0.9];
          }
        }

        rebuildSliders();
        updateCoords();
      });

      // Layout change rebuilds sliders
      if (layoutWidget) {
        const origCb = layoutWidget.callback;
        layoutWidget.callback = function (value) {
          const r = origCb?.apply(this, arguments);

          // Priority: existing custom coords > defaults
          const existingCoords = parseExistingCoords();
          if (!applyCoordsToSliders(existingCoords)) {
            if (value === "2-view") {
              vPositions = [imgW / 2];
            } else if (value === "2x2") {
              vPositions = [imgW / 2];
              hPosition = imgH / 2;
            } else if (value === "3-view") {
              vPositions = [imgW / 3, imgW * 2 / 3];
            } else {
              vPositions = [imgW / 2, imgW * 0.75, imgW * 0.9];
            }
          }

          rebuildSliders();
          updateCoords();
          return r;
        };
      }

      rebuildSliders();
      updateCoords();

      return r;
    };
  },
});
