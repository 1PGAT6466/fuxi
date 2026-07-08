const fs = require('fs');
const path = require('path');

const srcDir = 'E:\\easyclaw\\伏羲-v1.44\\repo\\frontend\\vue3-migration\\src';

// Validate specific findings

// 1. API Chat - "data" repeat (likely false positive: different scopes)
const chatLines = fs.readFileSync(path.join(srcDir, 'api', 'chat.ts'), 'utf-8').split('\n');
console.log('=== chat.ts: const data occurrences ===');
chatLines.forEach((l, i) => { if (/const\s+data\s*=/.test(l)) console.log(`  L${i+1}: ${l.trim().substring(0,80)}`); });

// 2. ServiceLoader "data"
const slLines = fs.readFileSync(path.join(srcDir, 'services', '_registry', 'ServiceLoader.ts'), 'utf-8').split('\n');
console.log('\n=== ServiceLoader.ts: const data ===');
slLines.forEach((l, i) => { if (/const\s+data\s*=/.test(l)) console.log(`  L${i+1}: ${l.trim().substring(0,80)}`); });

// 3. DxfCanvas worldX/worldY
const dcLines = fs.readFileSync(path.join(srcDir, 'services', 'dxf-viewer', 'DxfCanvas.vue'), 'utf-8').split('\n');
console.log('\n=== DxfCanvas.vue: worldX/Y definitions ===');
dcLines.forEach((l, i) => { if (/\b(worldX|worldY)\s*=/.test(l)) console.log(`  L${i+1}: ${l.trim().substring(0,80)}`); });

// 4. windowManager.ts calculateNextPosition
const wmLines = fs.readFileSync(path.join(srcDir, 'stores', 'windowManager.ts'), 'utf-8').split('\n');
console.log('\n=== windowManager.ts: calculateNextPosition ===');
wmLines.forEach((l, i) => { if (l.includes('calculateNextPosition')) console.log(`  L${i+1}: ${l.trim()}`); });

// 5. KnowledgeView "res" 
const kvLines = fs.readFileSync(path.join(srcDir, 'views', 'KnowledgeView.vue'), 'utf-8').split('\n');
console.log('\n=== KnowledgeView.vue: const res = ===');
kvLines.forEach((l, i) => { if (/const\s+res\s*=/.test(l)) console.log(`  L${i+1}: ${l.trim().substring(0,80)}`); });

// 6. Empty catch blocks (real check)
console.log('\n=== EMPTY CATCH BLOCKS (real scan) ===');
function scanForEmptyCatches(fp) {
  const content = fs.readFileSync(fp, 'utf-8');
  const lines = content.split('\n');
  // Check for catch block immediately followed by closing brace or empty statement
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    // catch (...) { ... } - same line
    if (/\bcatch\s*(\([^)]*\))?\s*\{\s*\}/.test(line)) {
      console.log(`  ${fp.replace(srcDir, 'src')} L${i+1}: empty catch - ${line.substring(0,80)}`);
      continue;
    }
    // Multi-line catch (...) { \n }
    if (/\bcatch\s*(\([^)]*\))?\s*\{/.test(line)) {
      // count lines until matching }
      let depth = 1;
      let j = i + 1;
      let contentInBlock = '';
      while (j < lines.length && depth > 0) {
        const nl = lines[j].trim();
        if (nl === '}' || nl === '};') depth--;
        else if (nl.includes('{')) depth++;
        if (depth > 0) contentInBlock += nl;
        j++;
      }
      // If block is empty or only has comments
      const isCommentOnly = contentInBlock.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '').trim() === '';
      if (isCommentOnly) {
        console.log(`  ${fp.replace(srcDir, 'src')} L${i+1}: empty multi-line catch block`);
      }
    }
  }
}
function collectFiles(dir, exts) { const res = []; for (const e of fs.readdirSync(dir, {withFileTypes:true})) { const fp = path.join(dir, e.name); if (e.isDirectory() && e.name !== '_archived') res.push(...collectFiles(fp, exts)); else if (e.isFile() && exts.includes(path.extname(e.name))) res.push(fp); } return res; }
const files = collectFiles(srcDir, ['.ts', '.vue']);
for (const f of files) scanForEmptyCatches(f);

// 7. Check sidebar routes that don't exist in router
console.log('\n=== SIDEBAR ROUTE EXISTENCE CHECK ===');
const routerContent = fs.readFileSync(path.join(srcDir, 'router', 'index.ts'), 'utf-8');
const registeredRoutes = [];
const routeRegex = /path\s*:\s*['"]([^'"]+)['"]/g;
let rm;
while ((rm = routeRegex.exec(routerContent)) !== null) { registeredRoutes.push(rm[1]); }

const wsContent = fs.readFileSync(path.join(srcDir, 'layouts', 'WorkspaceSidebar.vue'), 'utf-8');
const sidebarRoutes = [];
const srRegex = /route\s*:\s*['"]([^'"]+)['"]/g;
while ((rm = srRegex.exec(wsContent)) !== null) { sidebarRoutes.push(rm[1]); }

for (const sr of sidebarRoutes) {
  // Handle /workspace/ai-tools which is nested under / route
  const fullPath = sr === '/' ? '/' : sr;
  // Check if this exact path or a subpath exists
  const exists = registeredRoutes.some(r => r === fullPath || r === sr.replace('/', ''));
  if (!exists) {
    // Check if it's a nested child route path
    const segments = sr.split('/').filter(Boolean);
    const existsAsChild = registeredRoutes.some(r => r === segments[segments.length - 1] || r === sr.substring(1));
    console.log(`  WARNING: Sidebar route "${sr}" not found in router`);
  }
}

// 8. Service API endpoint alignment
console.log('\n=== SERVICE MANIFEST vs SERVICE API ALIGNMENT ===');
const services = ['ai-tools', 'data-analytics', 'doc-tools', 'dxf-viewer'];
for (const svc of services) {
  const mf = JSON.parse(fs.readFileSync(path.join(srcDir, 'services', svc, 'manifest.json'), 'utf-8'));
  const apiFile = path.join(srcDir, 'services', svc, 'api.ts');
  if (!fs.existsSync(apiFile)) { console.log(`  ${svc}: api.ts not found!`); continue; }
  const apiContent = fs.readFileSync(apiFile, 'utf-8');
  if (mf.endpoints) {
    for (const ep of mf.endpoints) {
      // Check if the endpoint path appears in the api file
      const pathPart = ep.path.replace('/health', '/health').replace(/\/\{[^}]+\}/g, '/');
      const found = apiContent.includes(ep.path);
      if (!found) {
        // Try without braces
        const plainPath = ep.path.replace(/\/\{[^}]+\}/g, '');
        const foundPlain = apiContent.includes(plainPath);
        if (!foundPlain) {
          console.log(`  ${svc}: endpoint ${ep.method} ${ep.path} NOT found in api.ts`);
        }
      }
    }
  }
  // Also check api.ts functions match manifest
  const funcRegex = /export\s+async\s+function\s+(\w+)/g;
  const apiFuncs = [];
  let fm;
  while ((fm = funcRegex.exec(apiContent)) !== null) { apiFuncs.push(fm[1]); }
}

// 9. Store API call verification - check if store actions call real API functions
console.log('\n=== STORE API CALL VERIFICATION ===');
// chat store calls functions from @/api/chat 
const cStore = fs.readFileSync(path.join(srcDir, 'stores', 'chat.ts'), 'utf-8');
const chatApiExports = ['fetchSessions', 'createSession', 'deleteSession', 'sendMessageStream', 'mockSendMessageStream'];
for (const fn of chatApiExports) {
  if (!cStore.includes(fn)) continue;
  // Check if it's actually imported
  if (cStore.includes(`{ ${fn}`) || cStore.includes(`{ fetchSessions,`) || cStore.includes(`import {`) && cStore.includes(`${fn}`)) {
    // likely imported
  }
}

// auth store
const aStore = fs.readFileSync(path.join(srcDir, 'stores', 'auth.ts'), 'utf-8');
const authImports = ['login', 'refreshToken', 'logout'];
for (const fn of authImports) {
  // verify
}

console.log('\n=== UNUSED IMPORTS (VUE TEMPLATE COMPONENTS) ===');
// Check if <Search> etc are used in templates
const mainLayout = fs.readFileSync(path.join(srcDir, 'layouts', 'MainLayout.vue'), 'utf-8');
const scriptStart = mainLayout.indexOf('<script');
const scriptEnd = mainLayout.lastIndexOf('</script>');
const templatePart = mainLayout.substring(0, scriptStart);
const scriptPart = mainLayout.substring(scriptStart, scriptEnd + 9);

// Find all icon imports
const iconImportRegex = /import\s*\{[^}]*\}\s*from\s*['"]@element-plus\/icons-vue['"]/g;
const allIconImports = [];
let iim;
while ((iim = iconImportRegex.exec(scriptPart)) !== null) {
  const names = iim[0].match(/\{([^}]*)\}/)[1].split(',').map(n => n.trim());
  allIconImports.push(...names);
}
allIconImports.forEach((name, idx) => {
  const tagRegex = new RegExp(`<${name}[\\s/>]`, 'g');
  const componentRegex = new RegExp(`<component\\s+[^>]*:is="[a-zA-Z]*${name}[a-zA-Z]*"`, 'g');
  const used = tagRegex.test(templatePart) || componentRegex.test(templatePart);
  if (!used && !templatePart.includes(`:is="item.icon"`)) {
    console.log(`  ${name} (L${idx}) - potentially unused icon import in MainLayout.vue`);
  }
});

console.log('\n=== DONE ===');
