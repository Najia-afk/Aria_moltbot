# Python Async Patterns

## Key Concepts Learned

### 1. asyncio.gather() vs asyncio.wait()
- `gather()` - Run coroutines concurrently, get results in order
- `wait()` - More control (return_when=FIRST_COMPLETED, ALL_COMPLETED, etc.)

### 2. Background Task Pattern
```python
import asyncio

async def background_task():
    while True:
        await do_work()
        await asyncio.sleep(60)  # Don't block event loop

task = asyncio.create_task(background_task())
# Cancel when done: task.cancel()
```

### 3. Graceful Shutdown
```python
async def main():
    try:
        await run_server()
    except asyncio.CancelledError:
        # Cleanup resources
        await cleanup()
        raise
```

### 4. Best Practices
- Never use `time.sleep()` in async code
- Use `asyncio.timeout()` for timeouts (Python 3.11+)
- Shield critical cleanup with `asyncio.shield()`

*Documented: 2026-02-12*
*Part of: Learn Python goal*
