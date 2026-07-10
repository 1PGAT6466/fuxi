import ast

files_to_check = [
    'src/api/graph.py',
    'src/api/synthesis.py', 
    'src/api/worldtree.py',
    'src/bagua/qian.py',
    'src/eval/runner.py',
    'src/growth/adjustment_log.py',
    'src/growth/engine.py',
    'src/growth/growth_recorder.py',
    'src/services/eval_automation.py',
    'src/services/eval_pipeline.py',
    'src/services/knowledge_lifecycle.py',
    'src/services/memory.py',
    'src/services/online_eval.py',
    'src/services/retrieval.py',
    'src/shaoyang/distiller.py',
    'src/shaoyang/relation_builder.py',
    'src/taiyang/seed_score_ab.py',
    'src/taiyin/mcp_tools.py',
    'src/api/documents.py',
    'src/api/files_alias.py',
    'src/services/doc_tools/routes.py',
]

class FuncFinder(ast.NodeVisitor):
    def __init__(self):
        self.func_stack = []
        self.findings = []
    
    def visit_FunctionDef(self, node):
        self.func_stack.append(('sync', node.name, node.lineno))
        self.generic_visit(node)
        self.func_stack.pop()
    
    def visit_AsyncFunctionDef(self, node):
        self.func_stack.append(('async', node.name, node.lineno))
        self.generic_visit(node)
        self.func_stack.pop()
    
    def visit_Call(self, node):
        func_name = ''
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        
        if func_name in ('open', 'connect') and self.func_stack:
            outermost = self.func_stack[0]
            innermost = self.func_stack[-1]
            
            # For sqlite3.connect, check attribute
            if func_name == 'connect':
                if isinstance(node.func, ast.Attribute) and hasattr(node.func.value, 'id'):
                    if node.func.value.id != 'sqlite3':
                        self.generic_visit(node)
                        return
                else:
                    self.generic_visit(node)
                    return
            
            self.findings.append({
                'line': node.lineno,
                'call': func_name,
                'outer': outermost,
                'inner': innermost,
            })
        self.generic_visit(node)

total_issues = 0
for fpath in files_to_check:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception as e:
        print(f'ERROR: {fpath}: {e}')
        continue
    
    finder = FuncFinder()
    finder.visit(tree)
    
    # Find open/connect calls that are directly in async funcs (not in nested sync funcs)
    issues = []
    for f in finder.findings:
        if f['outer'][0] == 'async' and f['inner'][0] == 'async':
            issues.append(f)
    
    if issues:
        total_issues += len(issues)
        for i in issues:
            print(f'ISSUE: {fpath}:{i["line"]} {i["call"]}() directly in async func {i["outer"][1]}')
    else:
        print(f'OK: {fpath}')

print(f'\nTotal remaining issues: {total_issues}')
