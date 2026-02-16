# SENTIMENT INTELLIGENCE SYSTEM
## Bidirectional Feedback with Reinforcement Learning

**Concept:** System analyzes sentiment → User validates/corrects → System learns → Improves over time

---

## 🎯 CORE IDEA

```
┌─────────────────────────────────────────────────────────────────┐
│                    SENTIMENT FEEDBACK LOOP                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Session JSONL ──▶ Auto Analysis ──▶ Confidence Score          │
│       │                              │                          │
│       │                              ▼                          │
│       │                         ┌─────────┐                     │
│       │                         │ System  │                     │
│       │                         │ Says:   │                     │
│       │                         │ "Frustrated (85%)"            │
│       │                         └────┬────┘                     │
│       │                              │                          │
│       ▼                              ▼                          │
│  ┌─────────┐                   ┌─────────┐                     │
│  │  HTML   │◀─────────────────│  User   │                     │
│  │Dashboard│  Validate/Correct │ Validates?                    │
│  │         │─────────────────▶│         │                     │
│  └────┬────┘                   └────┬────┘                     │
│       │                              │                          │
│       ▼                              ▼                          │
│  ┌───────────────────────────────────────┐                     │
│  │      REINFORCEMENT LEARNING ENGINE     │                     │
│  │  ┌─────────┐    ┌─────────┐          │                     │
│  │  │ Correct │───▶│ +Weight │          │                     │
│  │  │  Match  │    │  Update │          │                     │
│  │  └─────────┘    └─────────┘          │                     │
│  │                                         │                     │
│  │  ┌─────────┐    ┌─────────┐          │                     │
│  │  │ Incorrect│───▶│ -Weight │          │                     │
│  │  │  (User   │    │ Pattern │          │                     │
│  │  │  Fixed)  │    │  Update │          │                     │
│  │  └─────────┘    └─────────┘          │                     │
│  └───────────────────────────────────────┘                     │
│                              │                                  │
│                              ▼                                  │
│                    Improved Model for Next Session             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 DATA MODEL

### Session-Level Sentiment Analysis
```json
{
  "session_id": "uuid",
  "timestamp": "2026-02-16T17:00:00Z",
  "analysis": {
    "overall": {
      "valence": -0.65,
      "arousal": 0.78,
      "dominance": 0.42,
      "confidence": 0.85
    },
    "derived": {
      "frustration": 0.72,
      "satisfaction": 0.15,
      "confusion": 0.23,
      "primary_emotion": "frustrated"
    },
    "trajectory": "declining",
    "turning_points": [
      {"timestamp": "16:45", "valence_change": -0.4, "trigger": "error_message"}
    ]
  },
  "message_breakdown": [
    {
      "msg_id": 1,
      "timestamp": "16:30",
      "content_preview": "Could you help...",
      "sentiment": {"valence": 0.2, "arousal": 0.3},
      "weight": 1.0
    },
    {
      "msg_id": 5,
      "timestamp": "16:45",
      "content_preview": "This is not working!",
      "sentiment": {"valence": -0.8, "arousal": 0.9},
      "weight": 2.0  // Higher weight on strong sentiment
    }
  ],
  "feedback": {
    "user_validated": true,
    "user_correction": null,  // or {"primary_emotion": "confused", ...}
    "correction_reason": null, // "was_frustrated_not_angry"
    "learning_applied": true
  }
}
```

### Cross-Session Intelligence (Aggregated)
```json
{
  "user_id": "najia",
  "time_range": "2026-02-01 to 2026-02-16",
  "sentiment_profile": {
    "baseline_valence": 0.35,
    "baseline_arousal": 0.45,
    "volatile_sessions": ["uuid1", "uuid2"],
    "trend": "improving"
  },
  "patterns": [
    {
      "type": "time_based",
      "pattern": "frustration_peaks_at_17h",
      "confidence": 0.82,
      "occurrences": 8
    },
    {
      "type": "topic_based",
      "pattern": "high_satisfaction_with_coding_tasks",
      "confidence": 0.91,
      "occurrences": 15
    }
  ],
  "feedback_stats": {
    "total_analyses": 45,
    "user_validated": 38,
    "user_corrected": 7,
    "accuracy_rate": 0.84
  },
  "learning_progress": {
    "model_version": "v2.3",
    "improvement_since_baseline": "+12%",
    "last_trained": "2026-02-16T12:00:00Z"
  }
}
```

---

## 🖥️ HTML DASHBOARD

### Session Sentiment Report (Per Session)
```html
<!DOCTYPE html>
<html>
<head>
  <title>Session Sentiment Analysis</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    .sentiment-card { 
      border-radius: 8px; 
      padding: 20px; 
      margin: 10px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }
    .emotion-badge {
      display: inline-block;
      padding: 5px 15px;
      border-radius: 20px;
      font-weight: bold;
    }
    .frustrated { background: #ff6b6b; }
    .satisfied { background: #51cf66; }
    .confused { background: #ffd43b; color: #333; }
    .neutral { background: #868e96; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <h1>📊 Session Sentiment Analysis</h1>
    <p>Session: <code>2026-02-16-abc123</code> | Duration: 45 min | Messages: 12</p>
    
    <!-- Overall Sentiment -->
    <div class="sentiment-card">
      <h2>System Assessment</h2>
      <div class="emotion-badge frustrated">Frustrated (85%)</div>
      <p><strong>Confidence:</strong> 85%</p>
      <p><strong>Trend:</strong> ↘️ Declining (started neutral, ended frustrated)</p>
      <p><strong>Peak Emotion:</strong> 16:45 - "This is not working!"</p>
    </div>
    
    <!-- Dimensions -->
    <div class="row">
      <div class="col">
        <h3>Valence (Positive/Negative)</h3>
        <div class="progress-bar">
          <div class="progress-fill" style="width: 35%; background: #ff6b6b;">
            -0.65 (Negative)
          </div>
        </div>
      </div>
      <div class="col">
        <h3>Arousal (Calm/Excited)</h3>
        <div class="progress-bar">
          <div class="progress-fill" style="width: 78%; background: #ffa94d;">
            0.78 (High Energy)
          </div>
        </div>
      </div>
      <div class="col">
        <h3>Dominance (Submissive/Dominant)</h3>
        <div class="progress-bar">
          <div class="progress-fill" style="width: 42%; background: #74c0fc;">
            0.42 (Moderate)
          </div>
        </div>
      </div>
    </div>
    
    <!-- Trajectory Graph -->
    <canvas id="sentimentChart" width="800" height="300"></canvas>
    <script>
      // Chart showing valence over time
      // Red dots = frustration peaks
      // Green dots = satisfaction moments
    </script>
    
    <!-- Feedback Section -->
    <div class="feedback-section" style="background: #f8f9fa; padding: 20px; margin: 20px 0;">
      <h3>🎯 Validate Analysis</h3>
      <p>Does this match your experience in this session?</p>
      
      <form id="feedbackForm">
        <label>
          <input type="radio" name="validation" value="correct" checked>
          ✅ Correct - I was frustrated
        </label><br>
        
        <label>
          <input type="radio" name="validation" value="partial">
          ⚠️ Partially - I was more 
          <select name="correction">
            <option value="confused">Confused</option>
            <option value="satisfied">Satisfied</option>
            <option value="neutral">Neutral</option>
            <option value="angry">Angry (not frustrated)</option>
          </select>
        </label><br>
        
        <label>
          <input type="radio" name="validation" value="wrong">
          ❌ Wrong - Completely different emotion
        </label><br><br>
        
        <label>
          Context (optional):<br>
          <textarea name="context" placeholder="What was actually happening?" rows="3" cols="50"></textarea>
        </label><br><br>
        
        <button type="submit" style="background: #339af0; color: white; padding: 10px 20px; border: none; border-radius: 5px;">
          Submit Feedback
        </button>
      </form>
    </div>
    
    <!-- Learning Status -->
    <div class="learning-status" style="background: #e7f5ff; padding: 15px; border-radius: 5px;">
      <p><strong>🧠 Learning Status:</strong></p>
      <p>Your feedback has improved sentiment accuracy by <strong>+12%</strong> over 45 sessions.</p>
      <p>Pattern learned: "Najia's frustration peaks around 17:00 when dealing with bugs"</p>
    </div>
  </div>
</body>
</html>
```

---

## 🔄 REINFORCEMENT LEARNING ENGINE

### Simple Weight Adjustment Algorithm
```python
class SentimentLearningEngine:
    """
    Reinforcement learning for sentiment analysis.
    Adjusts weights based on user feedback.
    """
    
    def __init__(self):
        self.weights = {
            'lexicon': 0.3,
            'llm': 0.7,
            'pattern_match': 0.0  # Learned patterns
        }
        self.pattern_memory = {}  # user_patterns -> sentiment_bias
        
    async def analyze_with_feedback(self, session_data: dict) -> dict:
        """
        Analyze sentiment and store for feedback.
        """
        # 1. Get base analysis
        base_sentiment = await self._base_analysis(session_data)
        
        # 2. Apply learned patterns
        adjusted_sentiment = self._apply_learned_patterns(
            base_sentiment, 
            session_data
        )
        
        # 3. Store for user validation
        analysis_id = await self._store_analysis(
            session_data['session_id'],
            adjusted_sentiment,
            confidence=self._calculate_confidence(adjusted_sentiment)
        )
        
        return {
            'analysis': adjusted_sentiment,
            'analysis_id': analysis_id,
            'needs_validation': adjusted_sentiment['confidence'] < 0.8,
            'feedback_url': f'/sentiment/feedback/{analysis_id}'
        }
    
    async def process_feedback(self, analysis_id: str, feedback: dict):
        """
        Process user feedback and update model.
        """
        original = await self._get_analysis(analysis_id)
        
        if feedback['validation'] == 'correct':
            # Reinforce correct patterns
            self._reinforce_weights(original, strength=0.1)
            
        elif feedback['validation'] == 'partial':
            # Adjust toward user correction
            correction = feedback['correction']
            self._adjust_toward_correction(original, correction, strength=0.2)
            
        elif feedback['validation'] == 'wrong':
            # Significant adjustment needed
            self._adjust_toward_correction(original, correction, strength=0.5)
            
        # Store pattern for future
        await self._learn_pattern(original['session_context'], feedback)
    
    def _apply_learned_patterns(self, sentiment: dict, context: dict) -> dict:
        """
        Apply learned patterns to adjust sentiment.
        """
        # Example learned patterns:
        # - "Najia says 'not working' + evening = frustration (not confusion)"
        # - "Najia + coding tasks = high satisfaction"
        
        patterns = self._find_matching_patterns(context)
        
        for pattern in patterns:
            if pattern['confidence'] > 0.7:
                # Apply pattern bias
                sentiment = self._blend_sentiment(
                    sentiment,
                    pattern['sentiment_bias'],
                    weight=pattern['confidence'] * 0.3
                )
        
        return sentiment
    
    async def _learn_pattern(self, context: dict, feedback: dict):
        """
        Extract and store patterns from feedback.
        """
        # Extract features
        features = {
            'time_of_day': context['timestamp'].hour,
            'topic_keywords': self._extract_topics(context['content']),
            'user_state': context.get('ongoing_task'),
        }
        
        # Store pattern: features -> corrected_sentiment
        pattern_key = self._hash_features(features)
        
        if pattern_key not in self.pattern_memory:
            self.pattern_memory[pattern_key] = {
                'features': features,
                'sentiment_bias': feedback['correction'],
                'occurrences': 0,
                'confirmed': 0
            }
        
        self.pattern_memory[pattern_key]['occurrences'] += 1
        if feedback['validation'] in ['correct', 'partial']:
            self.pattern_memory[pattern_key]['confirmed'] += 1
```

---

## 📈 LEARNING METRICS

### Track Over Time
```python
class LearningMetrics:
    """
    Track how well the system is learning.
    """
    
    async def get_accuracy_trend(self, days: int = 30) -> dict:
        """
        Get accuracy improvement over time.
        """
        return {
            'baseline_accuracy': 0.72,  # Before any feedback
            'current_accuracy': 0.84,    # After 45 sessions of feedback
            'improvement': '+16%',
            'trend': 'improving',
            'by_category': {
                'frustration_detection': 0.91,  # High - user corrects often
                'satisfaction_detection': 0.78,  # Lower - harder to detect
                'confusion_detection': 0.82
            }
        }
    
    async def get_learned_patterns(self) -> list:
        """
        Get human-readable learned patterns.
        """
        return [
            {
                'pattern': 'Evening frustration (17:00-19:00)',
                'confidence': 0.87,
                'occurrences': 12,
                'validated': 11,
                'description': 'User tends to be frustrated in evening sessions, especially with bugs'
            },
            {
                'pattern': 'Coding task satisfaction',
                'confidence': 0.93,
                'occurrences': 23,
                'validated': 22,
                'description': 'User shows high satisfaction when working on coding/architecture tasks'
            },
            {
                'pattern': '"Not working" = frustration, not confusion',
                'confidence': 0.79,
                'occurrences': 8,
                'validated': 7,
                'description': 'When user says "not working", they are frustrated (not asking for help)'
            }
        ]
```

---

## 🚀 IMPLEMENTATION STEPS

### Phase 1: Basic Sentiment Storage (30 min)
1. Add sentiment analysis to session processing
2. Store in `session_sentiments` table
3. Generate simple HTML report

### Phase 2: Feedback Loop (1 hour)
1. Add feedback form to HTML
2. Create feedback API endpoint
3. Store corrections

### Phase 3: Learning Engine (2 hours)
1. Implement weight adjustment
2. Add pattern extraction
3. Create learning metrics dashboard

### Phase 4: Intelligence (Ongoing)
1. Cross-session pattern detection
2. Personalized sentiment baselines
3. Predictive sentiment (anticipate user state)

---

## 💡 KEY FEATURES

### For You (Najia)
- ✅ Visual sentiment dashboard per session
- ✅ Easy feedback (click, select, submit)
- ✅ See learning progress ("+12% accuracy")
- ✅ Learned patterns about you

### For Aria (System)
- ✅ Continuous improvement from feedback
- ✅ Pattern recognition across sessions
- ✅ Predictive capabilities
- ✅ Confidence scoring (knows when uncertain)

### Bidirectional
- 🔄 System says: "I think you were frustrated"
- 🔄 You say: "Actually, I was confused"
- 🔄 System learns: "'Not working' + context = confusion, not frustration"
- 🔄 Next time: Better prediction

---

## 📝 FILES TO CREATE

1. `sentiment_analyzer_v2.py` — with feedback loop
2. `sentiment_dashboard.html` — interactive HTML report
3. `learning_engine.py` — RL weight adjustment
4. `sentiment_intelligence_api.py` — endpoints
5. `session_sentiment_report.html` — template

---

**This creates a true learning system that gets better the more you use it!** ⚡️
