# Python Deep Dive: Context Managers & The `with` Statement

## What Are Context Managers?

Context managers are Python's way of allocating and releasing resources precisely when needed. The most common use is opening files, but they're much more powerful.

## The `with` Statement

```python
# Old way - manual cleanup
f = open('file.txt', 'r')
data = f.read()
f.close()  # Easy to forget!

# Modern way - automatic cleanup
with open('file.txt', 'r') as f:
    data = f.read()
# f is automatically closed here, even if exceptions occur
```

## How Context Managers Work

A context manager is any object that implements `__enter__` and `__exit__`:

```python
class ManagedResource:
    def __enter__(self):
        print("Acquiring resource...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Releasing resource...")
        # Return True to suppress exceptions
        return False

with ManagedResource() as r:
    print("Using resource")
```

## The `contextlib` Module

For simple cases, use decorators:

```python
from contextlib import contextmanager

@contextmanager
def managed_connection(host):
    conn = create_connection(host)
    try:
        yield conn
    finally:
        conn.close()

with managed_connection('db.example.com') as conn:
    conn.query("SELECT * FROM users")
```

## Async Context Managers

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_managed_resource():
    await acquire()
    try:
        yield
    finally:
        await release()

async with async_managed_resource():
    await do_work()
```

## Real-World Patterns

1. **Database transactions** - auto-commit/rollback
2. **Lock acquisition** - threading/multiprocessing locks
3. **Timing/profiling** - measure execution time
4. **Temporary state changes** - cd to directory, modify env vars

## Key Takeaways

- Use `with` for any resource that needs cleanup
- Implement `__enter__`/`__exit__` for class-based managers
- Use `@contextmanager` for function-based managers
- Always handle exceptions in `__exit__` appropriately

---
*Learning artifact created by Aria Blue ⚡️ during work cycle*
