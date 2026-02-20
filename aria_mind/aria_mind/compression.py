"""
Batch compression for multiple conversation turns.
Optimizes token usage by compressing redundant context.
Target: Reduce medium layer latency to <100ms.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class CompressionResult:
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compressed_content: str

class TurnCompressor:
    """Compresses multiple conversation turns intelligently."""
    
    def __init__(self, max_summary_length: int = 200):
        self.max_summary_length = max_summary_length
        self.common_patterns = [
            (r'\n+', '\n'),  # Normalize newlines
            (r'\s+', ' '),   # Normalize whitespace
            (r'```[\s\S]*?```', '[CODE_BLOCK]'),  # Replace code blocks
            (r'https?://\S+', '[URL]'),  # Replace URLs
        ]
    
    def compress_turns(self, turns: List[Dict[str, Any]]) -> CompressionResult:
        """Compress a list of conversation turns."""
        original_text = self._turns_to_text(turns)
        original_tokens = self._estimate_tokens(original_text)
        
        # Remove redundant system messages (keep only last)
        filtered_turns = self._deduplicate_system_messages(turns)
        
        # Summarize older turns, keep recent ones full
        compressed_turns = self._hierarchical_summarize(filtered_turns)
        
        compressed_text = self._turns_to_text(compressed_turns)
        compressed_tokens = self._estimate_tokens(compressed_text)
        
        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / max(original_tokens, 1),
            compressed_content=compressed_text
        )
    
    def _turns_to_text(self, turns: List[Dict[str, Any]]) -> str:
        """Convert turns to text for token estimation."""
        return '\n'.join(f"{t.get('role', 'user')}: {t.get('content', '')}" for t in turns)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (~4 chars per token)."""
        return len(text) // 4
    
    def _deduplicate_system_messages(self, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep only the most recent system message."""
        system_indices = [i for i, t in enumerate(turns) if t.get('role') == 'system']
        if len(system_indices) <= 1:
            return turns
        # Remove all but last system message
        to_remove = set(system_indices[:-1])
        return [t for i, t in enumerate(turns) if i not in to_remove]
    
    def _hierarchical_summarize(self, turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep recent turns full, summarize older ones."""
        if len(turns) <= 3:
            return turns
        
        # Keep last 3 turns full
        recent = turns[-3:]
        older = turns[:-3]
        
        # Summarize older turns
        summary = self._summarize_turns(older)
        
        return [{"role": "system", "content": f"[Earlier conversation: {summary}]"}] + recent
    
    def _summarize_turns(self, turns: List[Dict[str, Any]]) -> str:
        """Create a brief summary of older turns."""
        topics = set()
        for turn in turns:
            content = turn.get('content', '')
            # Extract key nouns/phrases (simplified)
            words = re.findall(r'\b[A-Z][a-z]+\b|\b[a-z]{5,}\b', content)
            topics.update(words[:3])  # Take first 3 words per turn
        
        summary = ', '.join(sorted(topics)[:5])
        return summary[:self.max_summary_length] or 'general discussion'

# Singleton instance
_compressor: Optional[TurnCompressor] = None

def get_compressor() -> TurnCompressor:
    global _compressor
    if _compressor is None:
        _compressor = TurnCompressor()
    return _compressor

def compress_conversation(turns: List[Dict[str, Any]]) -> CompressionResult:
    """Compress conversation turns - entry point."""
    return get_compressor().compress_turns(turns)
