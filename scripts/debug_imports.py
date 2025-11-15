import sys, traceback
print('cwd:', __import__('os').getcwd())
print('sys.path (first 10):')
for p in sys.path[:10]:
    print('  ', p)
print('\nAttempting to import package `tests`...')
try:
    import tests
    print('OK imported tests ->', tests)
    print('tests.__file__:', getattr(tests, '__file__', None))
except Exception:
    traceback.print_exc()

print('\nAttempting to import one test module by name...')
try:
    import importlib
    m = importlib.import_module('tests.test_feature_engineering')
    print('OK imported tests.test_feature_engineering ->', m)
    print('module file:', getattr(m, '__file__', None))
except Exception:
    traceback.print_exc()
