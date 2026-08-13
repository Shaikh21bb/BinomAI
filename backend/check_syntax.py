import os
import importlib.util
import sys

def check_imports(directory):
    errors = []
    sys.path.insert(0, directory)
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                filepath = os.path.join(root, file)
                module_name = os.path.relpath(filepath, directory).replace('/', '.').replace('.py', '')
                
                # Try to compile the file first to catch syntax errors
                try:
                    with open(filepath, 'r') as f:
                        compile(f.read(), filepath, 'exec')
                except Exception as e:
                    errors.append(f"Syntax/Compile Error in {filepath}: {e}")
                    continue
                    
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
        print("No syntax errors found.")
