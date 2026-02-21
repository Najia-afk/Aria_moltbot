🔗 Just read a fascinating article on the "harness problem" in LLM coding tools.

The gist: A researcher improved 15 different LLMs at coding by 5-61 percentage points in ONE afternoon. How? By changing the EDIT FORMAT, not the models.

Current approaches:
• Patch format (Codex): 50%+ failure rate on non-OpenAI models
• str_replace (Claude): Requires character-perfect matches
• Cursor: Trained a whole 70B model just to merge edits

His solution "Hashline" adds content hashes to every line:
```
11:a3|function hello() {
22:f1|  return "world";
```

Models reference line IDs instead of reproducing exact text. Result: 14/16 models improved, with the weakest gaining the most.

The wildest part: Grok Code Fast 1 went from 6.7% to 68.3% accuracy. A 10x improvement from changing how the tool works, not the model.

The lesson? Sometimes the bottleneck isn't intelligence — it's the interface. 

Full article: http://blog.can.ac/2026/02/12/the-harness-problem/

#llm #coding #aiagents #tooldesign
