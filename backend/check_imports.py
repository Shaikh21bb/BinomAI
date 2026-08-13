import os
import sys
import importlib
import traceback
import types

def check_imports(directory):
    errors = []
    sys.path.insert(0, directory)
    sys.path.insert(0, os.path.dirname(directory)) # add backend to path
    
    # Mock some problematic heavy dependencies to bypass pip install issues if needed
    for mod in ['celery', 'google.generativeai', 'openai', 'fitz', 'docx', 'passlib.context', 'jwt', 'redis.asyncio']:
        sys.modules[mod] = types.ModuleType(mod)
        if mod == 'celery':
            sys.modules[mod].Celery = type('Celery', (), {'conf': type('Conf', (), {'update': lambda **kwargs: None})(), 'task': lambda **kwargs: lambda f: f})
            sys.modules[mod].shared_task = lambda **kwargs: lambda f: f
        if mod == 'passlib.context':
            sys.modules[mod].CryptContext = type('CryptContext', (), {})
            
    sys.modules['google'] = types.ModuleType('google')
    sys.modules['google.generativeai'] = types.ModuleType('google.generativeai')
    sys.modules['redis'] = types.ModuleType('redis')
    
    # We will try to import everything. If we get ModuleNotFoundError for an external library, 
    # we can note it, but if we get it for an internal module, it's a bug.
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                filepath = os.path.join(root, file)
                module_name = os.path.relpath(filepath, directory).replace('/', '.').replace('.py', '')
                full_module = f"app.{module_name}"
                
                try:
                    importlib.import_module(full_module)
                except Exception as e:
                    errors.append(f"Error importing {full_module}: {type(e).__name__}: {e}")
                    
    return errors

if __name__ == "__main__":
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app'))
    errors = check_imports(app_dir)
    if errors:
        print("Found errors:")
        for err in errors:
            print(err)
        sys.exit(1)
    else:
        print("All modules imported successfully.")
