const pptxgen = require("pptxgenjs");
const path = require("path");

// --- Design tokens (matching the project's own dashboard palette) --------
const BG_DARK = "0A0E1A";
const CARD = "131826";
const CARD_BORDER = "232B3D";
const TEXT_MAIN = "F4F6FB";
const TEXT_MUTED = "9AA4BF";
const ACCENT = "6D5EF5";
const ACCENT_LIGHT = "8B7CFF";
const TEAL = "22D3B6";
const AMBER = "F5A623";
const RED = "EF4444";
const BLUE = "3B82F6";

const FONT_HEAD = "Arial";
const FONT_BODY = "Arial";

function newDeck() {
  const p = new pptxgen();
  p.layout = "LAYOUT_WIDE"; // 13.3 x 7.5"
  return p;
}

function bgSlide(pres) {
  const s = pres.addSlide();
  s.background = { color: BG_DARK };
  return s;
}

function kicker(slide, text, opts = {}) {
  slide.addText(text.toUpperCase(), {
    x: opts.x ?? 0.6, y: opts.y ?? 0.45, w: opts.w ?? 8, h: 0.35,
    fontFace: FONT_BODY, fontSize: 13, color: ACCENT_LIGHT, bold: true,
    charSpacing: 2, margin: 0,
  });
}

function title(slide, text, opts = {}) {
  slide.addText(text, {
    x: opts.x ?? 0.6, y: opts.y ?? 0.78, w: opts.w ?? 11.8, h: opts.h ?? 0.9,
    fontFace: FONT_HEAD, fontSize: opts.size ?? 34, color: TEXT_MAIN, bold: true,
    margin: 0,
  });
}

function pageNum(slide, n) {
  slide.addText(String(n).padStart(2, "0"), {
    x: 12.55, y: 7.05, w: 0.6, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: TEXT_MUTED, align: "right", margin: 0,
  });
  slide.addText("SMART CLASSROOM", {
    x: 0.6, y: 7.05, w: 4, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: TEXT_MUTED, margin: 0, charSpacing: 1,
  });
}

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape("roundRect", {
    x, y, w, h,
    rectRadius: 0.08,
    fill: { color: opts.fill ?? CARD },
    line: { color: opts.line ?? CARD_BORDER, width: 1 },
    shadow: opts.shadow === false ? undefined : {
      type: "outer", color: "000000", opacity: 0.35, blur: 10, offset: 3, angle: 90,
    },
  });
}

// ---------------------------------------------------------------------
const pres = newDeck();
let n = 0;

// ===== Slide 1: Title =====
{
  const s = bgSlide(pres);
  n++;
  // Subtle radial-feel accent block (no stripe, a soft corner glow via shape)
  s.addShape("ellipse", {
    x: 8.8, y: -2.5, w: 8, h: 8, fill: { color: ACCENT, transparency: 88 }, line: { type: "none" },
  });
  s.addText("SMART CLASSROOM", {
    x: 0.9, y: 2.5, w: 10, h: 0.5,
    fontFace: FONT_BODY, fontSize: 15, color: ACCENT_LIGHT, bold: true, charSpacing: 3, margin: 0,
  });
  s.addText("AI-Powered Engagement &\nAttention Tracking System", {
    x: 0.9, y: 3.0, w: 10.5, h: 1.9,
    fontFace: FONT_HEAD, fontSize: 46, color: TEXT_MAIN, bold: true, margin: 0, lineSpacing: 52,
  });
  s.addText("Computer Vision  •  Deep Learning  •  IoT  •  Full-Stack Engineering", {
    x: 0.9, y: 4.85, w: 10, h: 0.5,
    fontFace: FONT_BODY, fontSize: 16, color: TEXT_MUTED, margin: 0,
  });
  s.addText("Final Year Project  |  Department of Computer Science and Engineering", {
    x: 0.9, y: 6.7, w: 9, h: 0.4,
    fontFace: FONT_BODY, fontSize: 12, color: TEXT_MUTED, margin: 0,
  });
}

// ===== Slide 2: Problem =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "The Problem");
  title(s, "Engagement is invisible at classroom scale");
  const points = [
    ["No objective signal", "Instructors rely on a visual scan of the room — subjective, unrecorded, and impossible to scale past ~20-30 students."],
    ["No early warning", "Disengagement (drowsiness, distraction) is noticed only after it has already cost learning time."],
    ["No longitudinal data", "Nothing is logged, so patterns across a semester — or across a whole class — are invisible."],
  ];
  const colW = 3.75, gap = 0.35, startX = 0.6, y = 2.2, h = 3.9;
  points.forEach((pt, i) => {
    const x = startX + i * (colW + gap);
    card(s, x, y, colW, h);
    s.addText(String(i + 1).padStart(2, "0"), {
      x: x + 0.3, y: y + 0.3, w: 1.5, h: 0.6,
      fontFace: FONT_HEAD, fontSize: 26, color: ACCENT_LIGHT, bold: true, margin: 0,
    });
    s.addText(pt[0], {
      x: x + 0.3, y: y + 1.0, w: colW - 0.6, h: 0.7,
      fontFace: FONT_HEAD, fontSize: 19, color: TEXT_MAIN, bold: true, margin: 0,
    });
    s.addText(pt[1], {
      x: x + 0.3, y: y + 1.7, w: colW - 0.6, h: h - 2.0,
      fontFace: FONT_BODY, fontSize: 13, color: TEXT_MUTED, margin: 0, lineSpacing: 19,
    });
  });
  pageNum(s, n);
}

// ===== Slide 3: Objectives =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "Objectives");
  title(s, "What the system sets out to do");
  const objs = [
    "Real-time multi-face detection & landmark tracking on a standard webcam",
    "A configurable weighted attention-scoring engine — not hardcoded thresholds",
    "Automated attendance via face recognition",
    "Cloud-persisted analytics (Firestore) for longitudinal insight",
    "A live dashboard for instructors, plus optional IoT hardware alerts",
  ];
  let y = 1.95;
  objs.forEach((obj, i) => {
    const rowH = 0.76;
    card(s, 0.6, y, 12.1, rowH, { shadow: false });
    s.addShape("roundRect", {
      x: 0.85, y: y + rowH / 2 - 0.17, w: 0.34, h: 0.34, rectRadius: 0.17,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(String(i + 1), {
      x: 0.85, y: y + rowH / 2 - 0.17, w: 0.34, h: 0.34,
      fontFace: FONT_BODY, fontSize: 13, color: TEXT_MAIN, bold: true, align: "center", valign: "middle", margin: 0,
    });
    s.addText(obj, {
      x: 1.4, y, w: 10.9, h: rowH,
      fontFace: FONT_BODY, fontSize: 16, color: TEXT_MAIN, valign: "middle", margin: 0,
    });
    y += rowH + 0.14;
  });
  pageNum(s, n);
}

// ===== Slide 4: Architecture =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "System Architecture");
  title(s, "Layered, dependency-injected pipeline");

  const layers = [
    { label: "Client", items: ["React Dashboard", "Webcam Capture"], color: BLUE },
    { label: "API", items: ["Flask REST API", "Classroom Pipeline"], color: ACCENT },
    { label: "CV Modules", items: ["Face Detect/Recognize", "Eye Track • Head Pose", "Sleep/Yawn • Attention"], color: TEAL },
    { label: "Persistence", items: ["Firestore", "Attendance • Alerts"], color: AMBER },
    { label: "Hardware", items: ["ESP32", "LED • Buzzer • LCD"], color: RED },
  ];
  const colW = 2.28, gap = 0.18, startX = 0.6, y = 2.15, h = 4.1;
  layers.forEach((layer, i) => {
    const x = startX + i * (colW + gap);
    card(s, x, y, colW, h, { shadow: false });
    s.addShape("ellipse", {
      x: x + 0.22, y: y + 0.28, w: 0.16, h: 0.16,
      fill: { color: layer.color }, line: { type: "none" },
    });
    s.addText(layer.label, {
      x: x + 0.48, y: y + 0.2, w: colW - 0.66, h: 0.34,
      fontFace: FONT_HEAD, fontSize: 15, color: TEXT_MAIN, bold: true, margin: 0, valign: "middle",
    });
    let iy = y + 1.0;
    layer.items.forEach((it) => {
      s.addText(it, {
        x: x + 0.2, y: iy, w: colW - 0.4, h: 0.7,
        fontFace: FONT_BODY, fontSize: 11.5, color: TEXT_MUTED, margin: 0, lineSpacing: 15,
      });
      iy += 0.75;
    });
  });
  // Draw connector arrows in a second pass so they aren't drawn under the
  // next card (pptxgenjs stacks shapes in add-order, and each card in the
  // loop above would otherwise paint over the previous column's arrow).
  layers.forEach((layer, i) => {
    if (i === layers.length - 1) return;
    const x = startX + i * (colW + gap);
    s.addText("\u203A", {
      x: x + colW - 0.03, y: y + h / 2 - 0.3, w: gap + 0.06, h: 0.6,
      fontFace: FONT_HEAD, fontSize: 24, color: ACCENT_LIGHT, bold: true, align: "center", valign: "middle", margin: 0,
    });
  });
  pageNum(s, n);
}

// ===== Slide 5: Attention Scoring Algorithm =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "The Core Algorithm");
  title(s, "A weighted, configurable attention score");

  card(s, 0.6, 2.15, 5.7, 4.15, { shadow: false });
  s.addText("Seven signals, one score (0-100)", {
    x: 0.95, y: 2.4, w: 5.1, h: 0.5, fontFace: FONT_HEAD, fontSize: 16, bold: true, color: TEXT_MAIN, margin: 0,
  });
  const weights = [
    ["Eye Aspect Ratio", "20%", TEAL],
    ["Head Pose", "20%", BLUE],
    ["Face Presence", "15%", ACCENT_LIGHT],
    ["Sleep Duration", "15%", RED],
    ["Blink Rate", "10%", AMBER],
    ["Yawn Count", "10%", AMBER],
    ["Emotion", "10%", TEXT_MUTED],
  ];
  let wy = 3.0;
  weights.forEach(([label, pct, color]) => {
    s.addText(label, { x: 0.95, y: wy, w: 2.6, h: 0.34, fontFace: FONT_BODY, fontSize: 12.5, color: TEXT_MAIN, margin: 0, valign: "middle" });
    const barMaxW = 2.1;
    const frac = parseInt(pct) / 20;
    s.addShape("roundRect", { x: 3.65, y: wy + 0.07, w: barMaxW, h: 0.2, rectRadius: 0.1, fill: { color: CARD_BORDER }, line: { type: "none" } });
    s.addShape("roundRect", { x: 3.65, y: wy + 0.07, w: Math.max(barMaxW * frac, 0.12), h: 0.2, rectRadius: 0.1, fill: { color }, line: { type: "none" } });
    s.addText(pct, { x: 5.85, y: wy, w: 0.45, h: 0.34, fontFace: FONT_BODY, fontSize: 12, color: TEXT_MUTED, margin: 0, valign: "middle", align: "right" });
    wy += 0.42;
  });

  card(s, 6.55, 2.15, 6.15, 4.15, { shadow: false });
  s.addText("Formula", {
    x: 6.9, y: 2.4, w: 5.5, h: 0.5, fontFace: FONT_HEAD, fontSize: 16, bold: true, color: TEXT_MAIN, margin: 0,
  });
  s.addText([
    { text: "A = \u03A3 w", options: { fontSize: 20, color: ACCENT_LIGHT } },
    { text: "i", options: { fontSize: 13, color: ACCENT_LIGHT, subscript: true } },
    { text: " \u00B7 S", options: { fontSize: 20, color: ACCENT_LIGHT } },
    { text: "i", options: { fontSize: 13, color: ACCENT_LIGHT, subscript: true } },
    { text: " ,   subject to  \u03A3 w", options: { fontSize: 20, color: ACCENT_LIGHT } },
    { text: "i", options: { fontSize: 13, color: ACCENT_LIGHT, subscript: true } },
    { text: " = 1", options: { fontSize: 20, color: ACCENT_LIGHT } },
  ], { x: 6.9, y: 3.05, w: 5.6, h: 0.6, fontFace: "Courier New", bold: true, margin: 0 });
  s.addText("Each raw signal Si is normalized to 0-100 by a piecewise-linear function against configured thresholds, then combined by weight and smoothed across frames by exponential moving average \u2014 preventing single-frame jitter from swinging the score.", {
    x: 6.9, y: 3.8, w: 5.5, h: 1.3, fontFace: FONT_BODY, fontSize: 13, color: TEXT_MUTED, margin: 0, lineSpacing: 19,
  });
  s.addText("All weights & thresholds live in attention_weights.json \u2014 retune without touching code.", {
    x: 6.9, y: 5.35, w: 5.5, h: 0.7, fontFace: FONT_BODY, fontSize: 12.5, italic: true, color: TEAL, margin: 0, lineSpacing: 17,
  });
  pageNum(s, n);
}

// ===== Slide 6: Live Dashboard (screenshot) =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "Live Dashboard");
  title(s, "Real-time monitoring for instructors");
  card(s, 0.6, 2.15, 12.1, 4.55, { shadow: true });
  s.addImage({
    path: path.join(__dirname, "dashboard_reference.png"),
    x: 0.75, y: 2.3, w: 11.8, h: 4.25, sizing: { type: "contain", w: 11.8, h: 4.25 },
  });
  pageNum(s, n);
}

// ===== Slide 7: Hardware =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "Hardware Integration");
  title(s, "ESP32-driven physical alerts");

  card(s, 0.6, 2.15, 5.8, 4.15, { shadow: false });
  s.addText("Components", { x: 0.95, y: 2.4, w: 5, h: 0.4, fontFace: FONT_HEAD, fontSize: 16, bold: true, color: TEXT_MAIN, margin: 0 });
  const hw = ["ESP32 DevKit V1", "3x status LED (green / yellow / red)", "Active piezo buzzer", "16x2 I2C LCD", "Reserved GPIO for future servo"];
  let hy = 2.95;
  hw.forEach((item) => {
    s.addText("\u2022  " + item, { x: 0.95, y: hy, w: 5.2, h: 0.4, fontFace: FONT_BODY, fontSize: 14, color: TEXT_MUTED, margin: 0 });
    hy += 0.5;
  });

  card(s, 6.6, 2.15, 6.1, 4.15, { shadow: false });
  s.addText("JSON Command Protocol", { x: 6.95, y: 2.4, w: 5.5, h: 0.4, fontFace: FONT_HEAD, fontSize: 16, bold: true, color: TEXT_MAIN, margin: 0 });
  s.addText(
    '{\n  "cmd": "alert",\n  "severity": "critical",\n  "led": "red",\n  "buzzer_ms": 800,\n  "lcd_line1": "ALERT",\n  "lcd_line2": "Low Attention"\n}',
    { x: 6.95, y: 2.95, w: 5.5, h: 2.5, fontFace: "Courier New", fontSize: 13, color: TEAL, margin: 0.1, fill: { color: "0D1220" }, line: { color: CARD_BORDER, width: 1 } }
  );
  s.addText("POST over WiFi to the ESP32's local HTTP server \u2014 fails gracefully (logged, non-fatal) if hardware is offline.", {
    x: 6.95, y: 5.6, w: 5.5, h: 0.6, fontFace: FONT_BODY, fontSize: 12, italic: true, color: TEXT_MUTED, margin: 0, lineSpacing: 16,
  });
  pageNum(s, n);
}

// ===== Slide 8: Results =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "Validation");
  title(s, "Clear separation between attention states");

  s.addChart(pres.ChartType.bar, [
    {
      name: "Attention Score",
      labels: ["Fully Attentive", "Distracted", "Drowsy / Yawning"],
      values: [92.4, 58.0, 27.0],
    },
  ], {
    x: 0.6, y: 2.15, w: 7.3, h: 4.3,
    showTitle: true, title: "Attention Engine Output on Test Signal Profiles",
    titleColor: TEXT_MAIN, titleFontSize: 14,
    chartColors: [ACCENT_LIGHT, AMBER, RED],
    showLegend: false,
    showValue: true, dataLabelColor: TEXT_MAIN, dataLabelFontSize: 12, dataLabelPosition: "outEnd",
    catAxisLabelColor: TEXT_MUTED, catAxisLabelFontSize: 12,
    valAxisLabelColor: TEXT_MUTED, valAxisLabelFontSize: 11,
    valAxisMaxVal: 100, valGridLine: { color: CARD_BORDER, size: 1 },
    catGridLine: { style: "none" },
    plotArea: { fill: { color: BG_DARK } },
    chartArea: { fill: { color: BG_DARK } },
  });

  card(s, 8.15, 2.15, 4.55, 4.3, { shadow: false });
  s.addText("Automated Test Suite", { x: 8.5, y: 2.4, w: 4, h: 0.4, fontFace: FONT_HEAD, fontSize: 16, bold: true, color: TEXT_MAIN, margin: 0 });
  const stats = [["21 / 21", "assertions passing"], ["3", "modules under test"], ["0", "known open bugs"]];
  let sy = 3.0;
  stats.forEach(([num, label]) => {
    s.addText(num, { x: 8.5, y: sy, w: 1.6, h: 0.6, fontFace: FONT_HEAD, fontSize: 26, bold: true, color: TEAL, margin: 0 });
    s.addText(label, { x: 8.5, y: sy + 0.6, w: 3.7, h: 0.35, fontFace: FONT_BODY, fontSize: 12, color: TEXT_MUTED, margin: 0 });
    sy += 1.1;
  });
  pageNum(s, n);
}

// ===== Slide 9: Future Scope =====
{
  const s = bgSlide(pres); n++;
  kicker(s, "Future Scope");
  title(s, "Where this goes next");
  const items = [
    ["Edge Deployment", "Quantized on-device models for classroom-local hardware without a GPU server."],
    ["Servo-Actuated Camera", "Multi-angle coverage \u2014 firmware protocol already reserves a servo command slot."],
    ["Semester-Long Trends", "Longitudinal engagement modelling correlated with assessment outcomes."],
    ["Stronger Privacy", "Federated or on-device face-encoding storage beyond server-side Firestore."],
  ];
  const colW = 5.85, rowH = 1.75, gapX = 0.4, gapY = 0.35, startX = 0.6, startY = 2.15;
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (colW + gapX);
    const y = startY + row * (rowH + gapY);
    card(s, x, y, colW, rowH, { shadow: false });
    s.addText(it[0], { x: x + 0.3, y: y + 0.22, w: colW - 0.6, h: 0.45, fontFace: FONT_HEAD, fontSize: 16, bold: true, color: ACCENT_LIGHT, margin: 0 });
    s.addText(it[1], { x: x + 0.3, y: y + 0.72, w: colW - 0.6, h: 0.9, fontFace: FONT_BODY, fontSize: 13, color: TEXT_MUTED, margin: 0, lineSpacing: 18 });
  });
  pageNum(s, n);
}

// ===== Slide 10: Closing =====
{
  const s = bgSlide(pres); n++;
  s.addShape("ellipse", {
    x: -3, y: 4, w: 8, h: 8, fill: { color: ACCENT, transparency: 88 }, line: { type: "none" },
  });
  s.addText("Thank You", {
    x: 0.9, y: 2.9, w: 10, h: 1.1, fontFace: FONT_HEAD, fontSize: 44, bold: true, color: TEXT_MAIN, margin: 0,
  });
  s.addText("Smart Classroom \u2014 AI-Powered Engagement & Attention Tracking System", {
    x: 0.9, y: 3.95, w: 10.5, h: 0.5, fontFace: FONT_BODY, fontSize: 16, color: TEXT_MUTED, margin: 0,
  });
  s.addText("Questions & Discussion", {
    x: 0.9, y: 4.6, w: 8, h: 0.4, fontFace: FONT_BODY, fontSize: 13, color: ACCENT_LIGHT, bold: true, charSpacing: 2, margin: 0,
  });
}

pres.writeFile({ fileName: path.join(__dirname, "Smart_Classroom_Presentation.pptx") }).then(() => {
  console.log("Deck written OK");
});
