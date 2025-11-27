import ast
p = 'backend/services/model_registry.py'
src = open(p, 'r', encoding='utf-8').read()
tree = ast.parse(src, p)
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == 'ModelRegistry':
        print('Found ModelRegistry')
        for n in node.body:
            if isinstance(n, ast.FunctionDef):
                print(' -', n.name)
        break
else:
    print('ModelRegistry class not found')
