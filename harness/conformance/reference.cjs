// Render the CommonMark 0.31.2 spec examples and harness/conformance/cases.json with the
// reference implementation (commonmark.js 0.31.2). Usage: node reference.cjs <node_modules dir> > ref.json
const path = require("path"), fs = require("fs");
const nm = process.argv[2];
const cm = require(path.join(nm, "commonmark"));
const spec = require(path.join(nm, "commonmark-spec")).tests;
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "cases.json"), "utf8"));
const render = (s) => new cm.HtmlRenderer().render(new cm.Parser().parse(s));
process.stdout.write(JSON.stringify({
  spec: spec.map((e) => ({ id: `spec#${e.number}`, section: e.section, markdown: e.markdown, html: render(e.markdown) })),
  cases: cases.map((c) => ({ id: c.id, why: c.why, markdown: c.markdown, html: render(c.markdown) })),
}));
