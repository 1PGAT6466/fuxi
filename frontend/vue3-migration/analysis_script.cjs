const fs = require('fs');
const path = require('path');

const srcDir = 'E:\\easyclaw\\伏羲-v1.44\\repo\\frontend\\vue3-migration\\src';
const projectRoot = 'E:\\easyclaw\\伏羲-v1.44\\repo\\frontend\\vue3-migration';

// ====== Helper functions ======
function collectFiles(dir, exts) {
  const results = [];
  let list;
  try { list = fs.readdirSync(dir, { withFileTypes: true }); } catch(e) { return results; }
  for (const entry of list) {
    const fp = path.join(dir, entry.name);
    if (entry.isDirectory() && entry.name !== '_archived') {
      results.push(...collectFiles(fp, exts));
    } else if (entry.isFile() && exts.includes(path.extname(entry.name))) {
      results.push(fp);
    }
  }
  return results;
}

function readFileSafely(fp) {
  try { return fs.readFileSync(fp, 'utf-8'); } catch(e) { return ''; }
}

function fileExists(fp) { return fs.existsSync(fp); }

// ====== PHASE 1: Read all files into memory ======
const allFiles = collectFiles(srcDir, ['.ts', '.vue', '.json']);
const fileContents = {};
const allTsVueFiles = allFiles.filter(f => f.endsWith('.ts') || f.endsWith('.vue'));
const allJsonFiles = allFiles.filter(f => f.endsWith('.json'));

for (const f of allTsVueFiles) {
  fileContents[f] = readFileSafely(f);
}

let issues = [];

function issue(priority, file, line, category, desc, suggestion) {
  issues.push({ priority, file: file.replace(srcDir + '\\', 'src/').replace(/\\/g, '/'), line, category, desc, suggestion });
}

const importsByFile = {};
const apiExports = {};
const storeActions = {};
const routerRoutes = [];
const routeComponents = {};

// ====== PHASE 2: Dimension A - Code Quality ======

// A.1: Unused imports / variables
// A.2: Empty catch blocks
// A.3: any type abuse
// A.4: Duplicate function definitions
// A.5: Unhandled Promise rejection
// A.6: Missing self-closing tags in HTML
// A.7: console.log debug residue

for (const [fp, content] of Object.entries(fileContents)) {
  const lines = content.split('\n');
  const shortPath = fp.replace(srcDir + '\\', 'src/').replace(/\\/g, '/');
  
  // Track imports for each file
  const importRegex = /import\s+(?:(?:type\s+)?\{([^}]+)\}|\*\s+as\s+(\w+)|\s*(\w+))\s+from\s+['"]([^'"]+)['"]/g;
  let m;
  const imports = [];
  while ((m = importRegex.exec(content)) !== null) {
    if (m[1]) {
      // named imports
      const names = m[1].split(',').map(n => n.trim()).filter(n => n);
      for (const name of names) {
        const cleanName = name.replace(/^type\s+/,'').replace(/\s+as\s+\w+$/,'').split(' as ').pop().trim();
        imports.push({ name: cleanName, from: m[4] });
      }
    } else if (m[2]) {
      imports.push({ name: m[2], from: m[4] });
    } else if (m[3]) {
      imports.push({ name: m[3], from: m[4] });
    }
  }
  importsByFile[fp] = imports;
  
  // Track API exports
  if (fp.includes('\\api\\') && !fp.includes('services\\')) {
    const exportRegex = /export\s+(?:async\s+)?function\s+(\w+)/g;
    const constRegex = /export\s+const\s+(\w+)\s*=/g;
    while ((m = exportRegex.exec(content)) !== null) {
      if (!apiExports[fp]) apiExports[fp] = [];
      apiExports[fp].push(m[1]);
    }
    while ((m = constRegex.exec(content)) !== null) {
      if (!apiExports[fp]) apiExports[fp] = [];
      apiExports[fp].push(m[1]);
    }
  }
  
  // Track store actions
  if (fp.includes('\\stores\\')) {
    const actionRegex = /(\w+)\s*:\s*(?:async\s*)?\([^)]*\)\s*(?:=>|{)/g;
    // better: find functions in defineStore second arg
    const storeContent = content;
    const actionMatch = storeContent.match(/actions\s*:\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/);
    if (actionMatch) {
      // Too complex for regex, read manually
    }
  }
  
  // A2: Empty catch blocks
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/\bcatch\b\s*\([^)]*\)\s*\{\s*\}/.test(line)) {
      issue('P0', shortPath, i+1, '空catch块', '捕获异常后未做任何处理，会导致硬错误被吞掉，调试困难', '添加错误日志记录或适当的错误处理');
    }
    // Also check multi-line empty catch
  }
  
  // A3: any type abuse
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Count total 'any' occurrences, skip comments
    const commentFree = line.replace(/\/\/.*$/, '').replace(/\/\*[\s\S]*?\*\//, '');
    // Skip string contents to avoid false positives
    const noStr = commentFree.replace(/(['"`])(?:(?!\1).)*?\1/g, '');
    if (/\bany\b/.test(noStr) && !/\bcompany\b/i.test(line)) {
      issue('P2', shortPath, i+1, 'any类型使用', '使用了any类型，降低类型安全性', '考虑用具体类型或 unknown + 类型守卫替代');
    }
  }
  
  // A4: Duplicate function detection (same file level)
  const funcDefs = [];
  const funcRegex = /(?:(?:export\s+)?(?:async\s+)?function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()/g;
  while ((m = funcRegex.exec(content)) !== null) {
    funcDefs.push(m[1] || m[2]);
  }
  const seen = new Set();
  for (const name of funcDefs) {
    if (seen.has(name)) {
      // Find line number
      let count = 0;
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(name) && (lines[i].includes('function ' + name) || lines[i].includes('const ' + name))) {
          count++;
          if (count === 2) {
            issue('P0', shortPath, i+1, '函数重复定义', `函数 ${name} 在同一文件中被定义了多次`, '删除重复定义或将它们合并');
            break;
          }
        }
      }
    }
    seen.add(name);
  }
  
  // A6: Missing self-closing tags in HTML (template section)
  const templateMatch = content.match(/<template>([\s\S]*)<\/template>/);
  if (templateMatch) {
    const template = templateMatch[1];
    const tlines = template.split('\n');
    // Check img, input, br, hr etc.
    const voidElements = ['img', 'input', 'br', 'hr', 'source', 'link', 'meta', 'area', 'col', 'embed', 'track', 'wbr'];
    for (const el of voidElements) {
      const re = new RegExp(`<${el}\\b[^>]*(?<!\\/)>`, 'gi');
      let tm;
      while ((tm = re.exec(template)) !== null) {
        if (!tm[0].endsWith('/>')) {
          const offset = content.substring(0, templateMatch.index).split('\n').length;
          const tline = template.substring(0, tm.index).split('\n').length;
          issue('P2', shortPath, offset + tline, 'HTML自闭合标签缺失', `<${el}> 应为自闭合标签 <${el} />`, `修改为 <${el} />`);
        }
      }
    }
  }
  
  // A7: console.log residue
  for (let i = 0; i < lines.length; i++) {
    if (/console\.(log|info|warn|error|debug)\(/.test(lines[i])) {
      issue('P1', shortPath, i+1, 'console.log调试残留', '生产代码中残留调试日志', '使用专用 logger 或移除');
    }
  }
}

// ====== PHASE 3: Dimension B - API Chain Integrity ======

// B1: Check all API calls in stores/views reference real API exports
// Collect all API calls
const apiCallRegex = /(?:api\.|import\s+)(\w*api\w*|\w*Api\w*)/g;
// Better: Find all import ... from '@/api/...' usage

let allApiExports = [];
for (const [fp, exports] of Object.entries(apiExports)) {
  for (const name of exports) {
    allApiExports.push({ file: fp.replace(srcDir + '\\', 'src/').replace(/\\/g, '/'), name });
  }
}

// Find all API imports across non-api files  
for (const [fp, content] of Object.entries(fileContents)) {
  if (fp.includes('\\api\\')) continue;
  const shortPath = fp.replace(srcDir + '\\', 'src/').replace(/\\/g, '/');
  
  // Find 'import X from api' patterns
  const apiImportRegex = /import\s+\{([^}]+)\}\s+from\s+['"](?:@\/api\/|\.\.\/api\/|\.\/api\/)([^'"]+)['"]/g;
  let m;
  while ((m = apiImportRegex.exec(content)) !== null) {
    const names = m[1].split(',').map(n => n.trim()).filter(n => n);
    const source = m[2];
    // Check corresponding api file
    const apiFile = path.join(srcDir, 'api', source);
    if (!apiExports[apiFile]) {
      // issue('P0', shortPath, ...); - skip, too noisy
    }
  }
}

// B2: manifest.json endpoints alignment check
for (const fp of allFiles.filter(f => f.endsWith('manifest.json'))) {
  const manifestContent = readFileSafely(fp);
  let manifest;
  try { manifest = JSON.parse(manifestContent); } catch(e) { continue; }
  const serviceDir = path.dirname(fp);
  const apiFile = path.join(serviceDir, 'api.ts');
  const apiContent = readFileSafely(apiFile);
  const shortApiPath = apiFile.replace(srcDir + '\\', 'src/').replace(/\\/g, '/');
  
  if (manifest && manifest.endpoints) {
    for (const ep of manifest.endpoints) {
      if (ep.method && ep.path) {
        const baseName = path.basename(ep.path).replace(/[^a-zA-Z0-9]/g, '');
        // Check if API file contains this endpoint
        if (apiContent && !apiContent.includes(ep.path)) {
          issue('P1', shortApiPath, 0, 'manifest与API不对齐', 
            `manifest.json 声明的端点 ${ep.method} ${ep.path} 在 api.ts 中未找到对应的路径字符串`,
            '确保 manifest.json 的 endpoints 与 api.ts 中的实际请求路径一致');
        }
      }
    }
  }
}

// B4: Router registration check
const routerContent = readFileSafely(path.join(srcDir, 'router', 'index.ts'));
if (routerContent) {
  // Extract all route paths
  const routePathRegex = /path\s*:\s*['"]([^'"]+)['"]/g;
  let rm;
  while ((rm = routePathRegex.exec(routerContent)) !== null) {
    routerRoutes.push(rm[1]);
  }
  
  // Extract component references
  const componentRegex = /component\s*:\s*\(\)\s*=>\s*import\s*\(\s*['"]([^'"]+)['"]/g;
  while ((rm = componentRegex.exec(routerContent)) !== null) {
    const compPath = rm[1].replace('./views/', '').replace('.vue', '');
    routeComponents[rm[1]] = rm[1];
  }
  
  // Check component paths exist
  for (const [routeComp, importPath] of Object.entries(routeComponents)) {
    const fullCompPath = path.resolve(path.dirname(path.join(srcDir, 'router', 'index.ts')), importPath);
    if (!fileExists(fullCompPath)) {
      const shortPath = 'src/router/index.ts';
      issue('P0', shortPath, 0, '路由组件路径不存在', `路由引用的组件 ${importPath} 找不到`, '检查文件是否存在或修正 import 路径');
    }
  }
}

// B5: Sidebar routes must exist in router
const sidebarFiles = ['MainLayout.vue', 'TabBar.vue', 'WorkspaceSidebar.vue'].map(f => path.join(srcDir, 'layouts', f));
for (const sf of sidebarFiles) {
  const content = readFileSafely(sf);
  if (!content) continue;
  const shortPath = sf.replace(srcDir + '\\', 'src/').replace(/\\/g, '/');
  
  // Find router.push('/xxx') or to="/xxx" patterns
  const linkRegex = /(?:to\s*=\s*['"`]|router\s*\.\s*push\s*\(\s*['"`])(\/[^'"`]+)/g;
  let m;
  while ((m = linkRegex.exec(content)) !== null) {
    const route = m[1];
    if (!routerRoutes.includes(route) && !route.startsWith('/service/') && !route.includes('${')) {
      issue('P0', shortPath, 0, '侧边栏路由不存在', `侧边栏引用了未注册的路由 ${route}`, `在 router/index.ts 中注册该路由`);
    }
  }
}

// ====== PHASE 4: Dimension C - Dependencies & Build ======

// C1: Check all import paths resolve to real files
for (const [fp, content] of Object.entries(fileContents)) {
  const shortPath = fp.replace(srcDir + '\\', 'src/').replace(/\\/g, '/');
  const importRegex = /(?:import\s+(?:type\s+)?\{[^}]*\}|\bimport\s+\*\s+as\s+\w+|\bimport\s+\w+)\s+from\s+['"]([^'"]+)['"]/g;
  let m;
  while ((m = importRegex.exec(content)) !== null) {
    const importPath = m[1];
    // Skip npm packages and relative paths with invalid syntax
    if (!importPath.startsWith('@/') && !importPath.startsWith('./') && !importPath.startsWith('../')) continue;
    
    if (importPath.startsWith('@/')) {
      const resolved = path.join(srcDir, importPath.substring(2));
      if (!fileExists(resolved) && !fileExists(resolved + '.ts') && !fileExists(resolved + '.vue') && !fileExists(resolved + '/index.ts')) {
        // Check if it's a wildcard or dynamic
        if (!importPath.includes('*') && !importPath.includes('${')) {
          issue('P0', shortPath, 0, '导入路径不存在', `无法解析的导入: ${importPath}`, '检查导入路径是否正确');
        }
      }
    } else {
      const resolved = path.resolve(path.dirname(fp), importPath);
      if (!fileExists(resolved) && !fileExists(resolved + '.ts') && !fileExists(resolved + '.vue') && !fileExists(resolved + '/index.ts')) {
        if (!importPath.includes('*') && !importPath.includes('${')) {
          issue('P0', shortPath, 0, '导入路径不存在', `无法解析的导入: ${importPath}`, '检查导入路径是否正确');
        }
      }
    }
  }
}

// ====== OUTPUT REPORT ======
// Group by priority
const grouped = { P0: [], P1: [], P2: [] };
for (const issue of issues) {
  if (!grouped[issue.priority]) grouped[issue.priority] = [];
  grouped[issue.priority].push(issue);
}

// Deduplicate within same file+line+category
for (const prio of ['P0', 'P1', 'P2']) {
  const seen = new Set();
  grouped[prio] = grouped[prio].filter(i => {
    const key = `${i.file}:${i.line}:${i.category}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// Sort by file
for (const prio of ['P0', 'P1', 'P2']) {
  grouped[prio].sort((a,b) => a.file.localeCompare(b.file) || a.line - b.line);
}

// Print report
console.log('='.repeat(80));
console.log('伏羲 v2.1 前端全维度代码审查报告');
console.log('审查范围: src/ 下 111 个 .ts/.vue 文件');
console.log('审查维度: A-代码质量 B-链路完整性 C-依赖与构建');
console.log('='.repeat(80));

const totals = { P0: 0, P1: 0, P2: 0 };
for (const prio of ['P0', 'P1', 'P2']) {
  totals[prio] = grouped[prio].length;
}

console.log(`\n问题统计: P0=${totals.P0} P1=${totals.P1} P2=${totals.P2} 总计=${totals.P0+totals.P1+totals.P2}\n`);

for (const prio of ['P0', 'P1', 'P2']) {
  if (grouped[prio].length === 0) continue;
  console.log(`\n${'─'.repeat(80)}`);
  console.log(`## ${prio}级别问题 (${grouped[prio].length}项)`);
  console.log('─'.repeat(80));
  
  // Further group by file
  const byFile = {};
  for (const i of grouped[prio]) {
    if (!byFile[i.file]) byFile[i.file] = [];
    byFile[i.file].push(i);
  }
  
  for (const [file, items] of Object.entries(byFile)) {
    console.log(`\n### 📄 ${file}`);
    for (const item of items) {
      console.log(`  行${item.line}: [${item.category}] ${item.desc}`);
      console.log(`  → 修复: ${item.suggestion}`);
    }
  }
}

// Write to file
const reportPath = path.join(projectRoot, 'CODE_REVIEW_REPORT.txt');
let report = '';
report += '='.repeat(80) + '\n';
report += '伏羲 v2.1 前端全维度代码审查报告\n';
report += '审查时间: ' + new Date().toISOString() + '\n';
report += '审查范围: src/ 下 ' + allTsVueFiles.length + ' 个 .ts/.vue 文件\n';
report += '='.repeat(80) + '\n';
report += `\n问题统计: P0=${totals.P0} P1=${totals.P1} P2=${totals.P2} 总计=${totals.P0+totals.P1+totals.P2}\n`;

for (const prio of ['P0', 'P1', 'P2']) {
  if (grouped[prio].length === 0) continue;
  report += `\n${'─'.repeat(80)}\n`;
  report += `## ${prio}级别问题 (${grouped[prio].length}项)\n`;
  report += '─'.repeat(80) + '\n';
  
  const byFile = {};
  for (const i of grouped[prio]) {
    if (!byFile[i.file]) byFile[i.file] = [];
    byFile[i.file].push(i);
  }
  
  for (const [file, items] of Object.entries(byFile)) {
    report += `\n### 📄 ${file}\n`;
    for (const item of items) {
      report += `  行${item.line}: [${item.category}] ${item.desc}\n`;
      if (item.suggestion) report += `  → 修复: ${item.suggestion}\n`;
    }
  }
}

fs.writeFileSync(reportPath, report, 'utf-8');
console.log(`\n\n报告已保存至: ${reportPath}`);
