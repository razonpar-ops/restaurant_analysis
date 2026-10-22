const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("/mnt/skills/public/pptx/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "deck_data.json"), "utf8"));
const S = D.stats;
const f0 = (x) => Math.round(x).toLocaleString("en-US");
const pc = (x) => Math.round(x * 100) + "%";

const THEME = {
  name: "Bangladesh Food Data",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: { dk1: "1F2D2A", lt1: "FFFFFF", dk2: "0B3D2E", lt2: "EAF3F0", accent1: "006A4E", accent2: "F42A41",
    accent3: "E9B44C", accent4: "8A9A95", accent5: "0B3D2E", accent6: "4FA38A", hlink: "006A4E", folHlink: "8A9A95" },
};
const HEX = { green: "006A4E", red: "F42A41", gold: "E9B44C", gray: "8A9A95", dark: "1F2D2A", deep: "0B3D2E", mint: "EAF3F0", grid: "DDE6E3" };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.title = "Bangladesh Restaurant Data";
pres.author = "Data analysis";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

async function icon(name, color = "#FFFFFF") {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(fa[name], { color, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: HEX.deep },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.2, w: 8.8, h: 1.3, fontSize: 44, bold: true, color: C.background1, align: "left", valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.6, w: 8.8, h: 0.7, fontSize: 18, color: C.background2, align: "left", valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.75, fontSize: 32, bold: true, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 9.1, y: 5.2, color: HEX.gray, fontSize: 10 },
});
pres.defineSlideMaster({
  title: "CLOSING_DARK", background: { color: HEX.deep },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.75, fontSize: 32, bold: true, color: C.background1, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 9.1, y: 5.2, color: HEX.gray, fontSize: 10 },
});

// ---------- helpers ----------
const card = (s, x, y, w, h, name) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: C.background2, width: 0 }, objectName: name });
const stat = (s, big, label, x, y, w, h, color, name, fs = 38) => {
  card(s, x, y, w, h, name + " card");
  s.addText(big, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: h * 0.55, fontSize: fs, bold: true, color: color || C.accent1, fontFace: "Cambria", align: "left", valign: "middle", margin: 0, isTextBox: true, objectName: name + " value" });
  s.addText(label, { x: x + 0.15, y: y + h * 0.62, w: w - 0.3, h: h * 0.34, fontSize: 14, color: C.text1, align: "left", valign: "top", margin: 0, isTextBox: true, objectName: name + " label" });
};
const chartBase = {
  catAxisLabelColor: HEX.dark, valAxisLabelColor: HEX.dark, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", dataLabelFontSize: 12, dataLabelColor: HEX.dark,
  valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" }, showValue: true, showLegend: false, titleFontFace: "+mn-lt", titleColor: HEX.dark, titleFontSize: 14,
};

(async () => {
  const ic = {
    copy: await icon("FaCopy"), zero: await icon("FaRegStar"), question: await icon("FaQuestion"), store: await icon("FaStore"),
  };

  // 1 ---- title
  pres.addSection({ title: "Overview" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Overview" });
  s.addText("Bangladesh Restaurant Data", { placeholder: "title" });
  s.addText("What is inside, what to trust, and what to watch out for", { placeholder: "body" });
  const trio = [[f0(S.unique_places), "unique places"], [f0(S.reviews_total), "reviews"], [pc(S.share_unrated), "unrated"]];
  trio.forEach(([b, l], i) => {
    const x = 0.6 + i * 3.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.8, w: 2.7, h: 1.2, rectRadius: 0.08, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: `Title stat card ${i + 1}` });
    s.addText(b, { x: x + 0.15, y: 3.85, w: 2.4, h: 0.65, fontSize: 32, bold: true, fontFace: "Cambria", color: C.background1, margin: 0, valign: "middle", isTextBox: true, objectName: `Title stat value ${i + 1}` });
    s.addText(l, { x: x + 0.15, y: 4.5, w: 2.4, h: 0.4, fontSize: 14, color: C.background2, margin: 0, valign: "top", isTextBox: true, objectName: `Title stat label ${i + 1}` });
  });
  s.addNotes(D.notes[0]);

  // 2 ---- at a glance
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Overview" });
  s.addText("The data at a glance", { placeholder: "title" });
  const g = [[f0(S.raw_rows), "raw rows in the file", C.accent4], [f0(S.unique_places), "unique places after cleaning", C.accent1],
    [f0(S.n_rated), "places with a star rating", C.accent1], [f0(S.reviews_total), "reviews in total", C.accent2]];
  g.forEach(([b, l, col], i) => stat(s, b, l, 0.5 + (i % 2) * 2.95, 1.3 + Math.floor(i / 2) * 1.75, 2.75, 1.55, col, `Glance ${i + 1}`));
  s.addText([
    { text: "8 columns", options: { bold: true, breakLine: true } },
    { text: "place_id, name, latitude, longitude, rating, number_of_reviews, affluence, address", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: `${S.india_rows} border places are in India (flagged)`, options: { breakLine: true } },
    { text: "Affluence = a 1-4 level, probably price (undocumented)" },
  ], { x: 6.55, y: 1.3, w: 2.95, h: 3.3, fontSize: 14, color: C.text1, valign: "top", margin: 0, paraSpaceAfter: 4, isTextBox: true, objectName: "Glance notes" });
  s.addNotes(D.notes[1]);

  // 3 ---- cleaning
  pres.addSection({ title: "Data quality" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data quality" });
  s.addText("What we had to clean", { placeholder: "title" });
  const cl = [
    ["copy", "15% duplicate rows", `${f0(S.raw_rows)} rows shrink to ${f0(S.unique_places)} unique places`],
    ["zero", "Rating 0 means none", `${f0(S.n_unrated)} places (${pc(S.share_unrated)}) have no rating and no reviews`],
    ["question", "Affluence is sparse", `${pc(1 - S.share_has_aff)} empty, and only filled for places with ${S.aff_min_reviews}+ reviews`],
    ["store", "Not all restaurants", `~${pc(S.non_rest_share)} look like shops, telecoms or schools (flagged)`],
  ];
  for (let i = 0; i < 4; i++) {
    const x = 0.5 + (i % 2) * 4.6, y = 1.25 + Math.floor(i / 2) * 1.95, [k, h, t] = cl[i];
    card(s, x, y, 4.4, 1.75, `Clean card ${i + 1}`);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.25, w: 0.65, h: 0.65, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: `Clean icon bg ${i + 1}` });
    s.addImage({ data: ic[k], x: x + 0.37, y: y + 0.42, w: 0.31, h: 0.31, altText: h });
    s.addText(h, { x: x + 1.05, y: y + 0.2, w: 3.2, h: 0.5, fontSize: 20, bold: true, color: C.text2, margin: 0, valign: "middle", fontFace: "Cambria", isTextBox: true, objectName: `Clean head ${i + 1}` });
    s.addText(t, { x: x + 1.05, y: y + 0.75, w: 3.2, h: 0.85, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: `Clean text ${i + 1}` });
  }
  s.addNotes(D.notes[2]);

  // 4 ---- ratings
  pres.addSection({ title: "Findings" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("Ratings are generous, with a spike at 5.0", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Places", labels: D.bands.map((b) => b[0]), values: D.bands.map((b) => b[1]) }], {
    ...chartBase, x: 0.5, y: 1.2, w: 6.0, h: 4.0, barDir: "col", chartColors: [HEX.gray, HEX.green, HEX.green, HEX.green, HEX.green, HEX.red],
    dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", showTitle: true, title: "Places by rating band", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40,
  });
  stat(s, S.rating_mean.toFixed(2), "average rating (rated places)", 6.8, 1.3, 2.7, 1.45, C.accent1, "Rating avg");
  stat(s, f0(S.n_five), "perfect 5.0s: the most common rating", 6.8, 2.95, 2.7, 1.45, C.accent2, "Rating five");
  s.addNotes(D.notes[3]);

  // 5 ---- 5.0 illusion
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("A perfect 5.0 usually means 1-2 reviews", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "% perfect 5.0", labels: D.bucket.map((b) => b[0]), values: D.bucket.map((b) => +b[1].toFixed(1)) }], {
    ...chartBase, x: 0.5, y: 1.2, w: 6.0, h: 4.0, barDir: "col", chartColors: [HEX.red, HEX.red, HEX.gold, HEX.green, HEX.green, HEX.green, HEX.green],
    dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', showTitle: true, title: "% of places with a perfect 5.0, by number of reviews", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40,
  });
  stat(s, pc(D.bucket[0][1] / 100), "of 1-review places score 5.0", 6.8, 1.3, 2.7, 1.45, C.accent2, "Five one");
  stat(s, "0", "perfect 5.0s among places with 50+ reviews", 6.8, 2.95, 2.7, 1.45, C.accent1, "Five fifty");
  s.addNotes(D.notes[4]);

  // 6 ---- concentration
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("A few places get most of the reviews", { placeholder: "title" });
  stat(s, pc(S.top1pct_share_reviews), "of reviews: top 1% of places", 0.5, 1.25, 3.0, 1.2, C.accent2, "Conc top1");
  stat(s, pc(S.top10pct_share_reviews), "of reviews: top 10% of places", 0.5, 2.6, 3.0, 1.2, C.accent1, "Conc top10");
  stat(s, String(Math.round(S.reviews_median)), "reviews at the median place", 0.5, 3.95, 3.0, 1.2, C.accent1, "Conc median");
  s.addChart(pres.charts.BAR, [{ name: "Places", labels: D.volume.map((b) => b[0]), values: D.volume.map((b) => b[1]) }], {
    ...chartBase, x: 3.8, y: 1.2, w: 5.7, h: 3.9, barDir: "col", chartColors: [HEX.gray, HEX.green, HEX.green, HEX.red],
    dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", showTitle: true, title: "Places by number of reviews", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40,
  });
  s.addNotes(D.notes[5]);

  // 7 ---- affluence
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("Affluence only exists for popular places", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "% with affluence", labels: D.aff_avail.map((b) => b[0]), values: D.aff_avail.map((b) => Math.round(b[1])) }], {
    ...chartBase, x: 0.5, y: 1.2, w: 6.0, h: 4.0, barDir: "col", chartColors: [HEX.green], dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"',
    showTitle: true, title: "% of places with an affluence value, by number of reviews", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 40,
  });
  stat(s, pc(S.share_has_aff), "of all places have affluence", 6.8, 1.3, 2.7, 1.45, C.accent1, "Aff share");
  stat(s, pc(S.aff_share_among_labeled["2"]), "of labelled places are level 2", 6.8, 2.95, 2.7, 1.45, C.accent2, "Aff lvl2");
  s.addNotes(D.notes[6]);

  // 8 ---- geography
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("Dhaka dominates the attention", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "map_density.png"), x: 0.4, y: 1.2, w: 4.0, h: 3.85, sizing: { type: "contain", w: 4.0, h: 3.85 }, altText: "Hex density map of restaurant locations across Bangladesh" });
  s.addChart(pres.charts.BAR, [{ name: "Places", labels: D.division.map((d) => d[0]).reverse(), values: D.division.map((d) => d[1]).reverse() }], {
    ...chartBase, x: 4.5, y: 1.15, w: 5.0, h: 2.55, barDir: "bar", chartColors: [HEX.green], dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0",
    showTitle: true, title: "Places by division", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 35, catAxisLabelFontSize: 11,
  });
  stat(s, pc(S.greater_dhaka_share), "of places in Greater Dhaka", 4.5, 3.85, 2.4, 1.2, C.accent1, "Geo places");
  stat(s, pc(S.gd_reviews_share), "of all reviews", 7.1, 3.85, 2.4, 1.2, C.accent2, "Geo reviews");
  s.addNotes(D.notes[7]);

  // 9 ---- names
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("What is in a name", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "Places", labels: D.keywords.map((d) => d[0]).reverse(), values: D.keywords.map((d) => d[1]).reverse() }], {
    ...chartBase, x: 0.5, y: 1.2, w: 5.8, h: 4.0, barDir: "bar", chartColors: [HEX.green], dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0",
    showTitle: true, title: "Places with the keyword in the name", valAxisHidden: true, valGridLine: { style: "none" }, barGapWidthPct: 35,
  });
  stat(s, pc(S.bengali_name_share), "of names are in Bengali script", 6.6, 1.3, 2.9, 1.45, C.accent1, "Name bengali");
  stat(s, `${pc(S.bengali_unrated_share)} vs ${pc(S.latin_unrated_share)}`, "unrated: Bengali vs English", 6.6, 2.95, 2.9, 1.45, C.accent2, "Name unrated", 28);
  s.addNotes(D.notes[8]);

  // 10 ---- top places
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
  s.addText("The standouts", { placeholder: "title" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.green }, fontSize: 12 } });
  const cell = (t, o = {}) => ({ text: String(t), options: { fontSize: 12, color: HEX.dark, ...o } });
  s.addText("Most reviewed", { x: 0.5, y: 1.15, w: 4.4, h: 0.4, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria", margin: 0, isTextBox: true, objectName: "Table head left" });
  s.addTable([[hdr("Place"), hdr("Reviews"), hdr("Rating")], ...D.top_reviews.map((r) => [cell(r[0]), cell(f0(r[1]), { align: "right" }), cell(r[2].toFixed(1), { align: "right" })])],
    { x: 0.5, y: 1.6, w: 4.4, colW: [2.5, 1.0, 0.9], rowH: 0.45, border: { type: "solid", color: HEX.grid, pt: 0.75 }, valign: "middle", autoPage: false });
  s.addText("Best rated, 500+ reviews (adjusted)", { x: 5.1, y: 1.15, w: 4.4, h: 0.4, fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria", margin: 0, isTextBox: true, objectName: "Table head right" });
  s.addTable([[hdr("Place"), hdr("Reviews"), hdr("Rating")], ...D.top_adj.map((r) => [cell(r[0]), cell(f0(r[1]), { align: "right" }), cell(r[2].toFixed(1), { align: "right" })])],
    { x: 5.1, y: 1.6, w: 4.4, colW: [2.5, 1.0, 0.9], rowH: 0.45, border: { type: "solid", color: HEX.grid, pt: 0.75 }, valign: "middle", autoPage: false });
  s.addText("English-script names only; full lists are in facts/08_top_lists.txt", { x: 0.5, y: 4.75, w: 9, h: 0.35, fontSize: 12, color: HEX.gray, margin: 0, isTextBox: true, objectName: "Table footnote" });
  s.addNotes(D.notes[9]);

  // 11 ---- takeaways
  pres.addSection({ title: "Wrap-up" });
  s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "Wrap-up" });
  s.addText("Five things to remember", { placeholder: "title" });
  const tk = [
    `${f0(S.raw_rows)} rows, but only ${f0(S.unique_places)} real places`,
    "A rating of 0 means no rating, not a bad score",
    "A perfect 5.0 usually means 1-2 reviews",
    "Reviews measure fame, concentrated in Dhaka",
    "Affluence covers only well-reviewed places",
  ];
  tk.forEach((t, i) => {
    const y = 1.25 + i * 0.77;
    s.addShape(pres.shapes.OVAL, { x: 0.5, y, w: 0.55, h: 0.55, fill: { color: C.accent2 }, line: { color: C.accent2, width: 0 }, objectName: `Take num bg ${i + 1}` });
    s.addText(String(i + 1), { x: 0.5, y, w: 0.55, h: 0.55, fontSize: 20, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `Take num ${i + 1}` });
    s.addText(t, { x: 1.3, y, w: 8.2, h: 0.55, fontSize: 20, color: C.background1, valign: "middle", margin: 0, isTextBox: true, objectName: `Take text ${i + 1}` });
  });
  s.addNotes(D.notes[10]);

  const out = path.join(ROOT, "restaurants_presentation.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
