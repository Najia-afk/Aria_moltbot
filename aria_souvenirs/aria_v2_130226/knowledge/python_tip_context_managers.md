# Python Tip: Context Managers

## The Pattern
Context managers (`with` statement) ensure proper resource handling.

## Basic Usage
```python
with open('file.txt', 'r') as f:
    content = f.read()
# File automatically closed, even if exception occurs
```

## Creating Your Own
```python
from contextlib import contextmanager

@contextmanager
def managed_resource():
    print("Acquiring...")
    yield "resource"
    print("Releasing...")

with managed_resource() as r:
    print(f"Using {r}")
```

## When to Use
- File I/O (built-in)
- Database connections
- Locks/threading
- Temporary state changes
- Anything with setup/teardown

## Benefits
- Cleaner than try/finally
- Exception-safe
- Readable intent
