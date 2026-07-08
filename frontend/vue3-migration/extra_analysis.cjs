const fs = require('fs');
const path = require('path');
const src = 'E:\\easyclaw\\伏羲-v1.44\\repo\\frontend\\vue3-migration\\src';

// Check FilePreview empty catch at L122
const fp = fs.readFileSync(path.join(src, "components/files/FilePreview.vue"), "utf-8");
const fplines = fp.split("\n");
console.log("=== FilePreview L115-130 ===");
for (let i = 115; i < Math.min(130, fplines.length); i++) {
  console.log(`L${i+1}: ${fplines[i]}`);
}

// Check the store actions in stores/auth.ts line 161 
console.log("\n=== auth.ts L155-170 ===");
const aLines = fs.readFileSync(path.join(src, "stores/auth.ts"), "utf-8").split("\n");
for (let i = 150; i < Math.min(175, aLines.length); i++) {
  console.log(`L${i+1}: ${aLines[i]}`);
}

// Check stores/chat.ts L148-175
console.log("\n=== chat store L145-175 ===");
const cLines = fs.readFileSync(path.join(src, "stores/chat.ts"), "utf-8").split("\n");
for (let i = 140; i < Math.min(180, cLines.length); i++) {
  console.log(`L${i+1}: ${cLines[i]}`);
}

// Check asset paths
console.log("\n=== ASSET PATH CHECK ===");
[
  "assets/styles/variables.scss",
  "assets/styles/main.scss", 
  "assets/styles/element-dark.scss",
  "styles/variables.css",
  "assets/styles/variables.css",
].forEach(p => {
  const fp = path.join(src, p);
  console.log(`  ${p}: ${fs.existsSync(fp) ? "OK" : "MISSING!"}`);
});

// Check for direct API calls in views (those without dedicated api.ts)
console.log("\n=== DIRECT API CALLS IN VIEWS (bypassing api layer) ===");
function findDirectApiCalls(fp) {
  const content = fs.readFileSync(fp, "utf-8");
  const shortPath = fp.replace(src + "\\", "src/").replace(/\\/g, "/");
  const apiCalls = [];
  const apiClientRegex = /apiClient\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = apiClientRegex.exec(content)) !== null) {
    apiCalls.push({ method: m[1], path: m[2] });
  }
  const fetchRegex = /\bfetch\s*\(\s*['"]([^'"]+)['"]/g;
  while ((m = fetchRegex.exec(content)) !== null) {
    apiCalls.push({ method: 'fetch', path: m[1] });
  }
  if (apiCalls.length > 0 && !shortPath.includes('api/')) {
    console.log(`  ${shortPath}:`);
    apiCalls.forEach(c => console.log(`    ${c.method} ${c.path}`));
  }
}
function collectFiles(dir, exts) { 
  const r = []; 
  for (const e of fs.readdirSync(dir,{withFileTypes:true})) { 
    if (e.isDirectory() && e.name !== "_archived") r.push(...collectFiles(path.join(dir,e.name), exts)); 
    else if (e.isFile() && exts.includes(path.extname(e.name))) r.push(path.join(dir,e.name)); 
  } 
  return r; 
}
const allFiles = collectFiles(src, [".ts", ".vue"]);
for (const f of allFiles) {
  if (f.includes("mock.ts") || f.includes("types.ts")) continue;
  findDirectApiCalls(f);
}

// Check stores/files.ts for direct api calls
console.log("\n=== stores/files.ts API calls ===");
const sf = fs.readFileSync(path.join(src, "stores/files.ts"), "utf-8");
const dirCalls = sf.match(/apiClient\.(get|post|delete)\s*\(\s*['"]([^'"]+)['"]/g) || [];
dirCalls.forEach(c => console.log(`  ${c}`));
