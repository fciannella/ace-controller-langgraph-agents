# Character Versioning System

## ✅ Simplified Structure: Base + Enhanced

We now use a clean **two-version system** for each character:

### Current Implementation
- **`base`** - Standard, reliable version (60% of users)
- **`enhanced`** - Improved version with deeper capabilities (40% of users)

### Live Agents
```
✅ buchwurm-plato-base       → Plato with standard philosophical engagement
✅ buchwurm-plato-enhanced   → Plato with deeper philosophical complexity
✅ buchwurm-terry-base       → Terry with classic wit and humor  
✅ buchwurm-terry-enhanced   → Terry with enhanced storytelling and humor
```

---

## Overview

The Buchwurm platform now supports multiple versions of the same character running simultaneously. This allows for A/B testing, gradual feature rollouts, and experimentation with different character personalities.

## Version IDs (Not Numerical)

Instead of numerical versions (1.0, 1.1, etc.), we use meaningful **Version IDs** that describe the character variant:

### Plato Versions
- **`base`** - The standard, proven version of Plato (60% of users)
- **`enhanced`** - Enhanced philosophical depth and reasoning (40% of users) 

### Terry Pratchett Versions
- **`base`** - The standard Terry Pratchett personality (60% of users)
- **`enhanced`** - Enhanced wit and storytelling depth (40% of users)

## Directory Structure

```
agents/
├── buchwurm-plato-base/            # Plato base version
├── buchwurm-plato-enhanced/        # Plato enhanced version  
├── buchwurm-terry-base/            # Terry base version
├── buchwurm-terry-enhanced/        # Terry enhanced version
└── langgraph.json                  # Configuration for all versions
```

## Agent Naming Convention

- **Base Character ID**: `plato`, `terry` (groups versions together)
- **Version ID**: `base`, `enhanced`
- **Agent Directory**: `buchwurm-{base_character_id}-{version_id}/`
- **Agent Identifier**: `buchwurm-{base_character_id}-{version_id}`

## Version Assignment

### Automatic Assignment
Users are automatically assigned versions based on configurable strategies:

```typescript
// Example configuration
{
  base_character_id: 'plato',
  available_version_ids: ['base', 'enhanced'],
  default_version_id: 'base',
  assignment_strategy: {
    method: 'weighted',
    weights: {
      'base': 0.6,        // 60% get base version
      'enhanced': 0.4     // 40% get enhanced version
    }
  }
}
```

### Assignment Methods
- **`weighted`** - Probabilistic assignment based on weights
- **`random`** - Random assignment across available versions
- **`manual`** - Manually assigned by admin/user
- **`experiment`** - A/B test assignment with control/test groups

### Sticky Assignment
Once assigned, users maintain their version assignment across sessions unless manually changed.

## Event Logging

All interactions are logged with version information for analytics:

```typescript
{
  event_id: "uuid",
  user_id: "user123",
  base_character_id: "plato", 
  character_version_id: "enhanced",
  event_type: "message_sent",
  timestamp: "2024-01-20T10:30:00Z",
  metadata: {
    message_length: 150,
    response_time_ms: 1200
  }
}
```

## Creating New Versions

### 1. Create Agent Directory
```bash
mkdir agents/buchwurm-plato-experimental
```

### 2. Copy Base Files
```bash
cp agents/buchwurm-plato-base/* agents/buchwurm-plato-experimental/
```

### 3. Update Agent Implementation
- Modify prompt file for new personality
- Update agent logger name
- Adjust any version-specific behavior

### 4. Update LangGraph Configuration
```json
{
  "graphs": {
    "buchwurm-plato-base": "./buchwurm-plato-base/plato-agent-base.py:agent",
    "buchwurm-plato-enhanced": "./buchwurm-plato-enhanced/plato-agent-enhanced.py:agent", 
    "buchwurm-terry-base": "./buchwurm-terry-base/terry-agent-base.py:agent",
    "buchwurm-terry-enhanced": "./buchwurm-terry-enhanced/terry-agent-enhanced.py:agent"
  }
}
```

### 5. Update Frontend Configuration
```typescript
// In VersionAssignmentService
this.versionConfigs.set('plato', {
  base_character_id: 'plato',
  available_version_ids: ['base', 'enhanced'],
  default_version_id: 'base',
  assignment_strategy: {
    method: 'weighted',
    weights: {
      'base': 0.6,        // 60% get base version
      'enhanced': 0.4     // 40% get enhanced version
    }
  }
});
```

## Benefits

### For Development
- **Gradual Rollouts**: Test new features with small user groups
- **A/B Testing**: Compare performance between versions
- **Risk Mitigation**: Keep stable version while experimenting
- **Feature Flags**: Enable/disable features per version

### For Users  
- **Personalization**: Different interaction styles for different preferences
- **Consistency**: Stable experience with assigned version
- **Quality**: Proven stable versions alongside innovative experiments

### For Analytics
- **Performance Comparison**: Compare metrics across versions
- **User Preferences**: Understand which versions users prefer
- **Conversion Tracking**: Track how versions affect user engagement
- **Quality Metrics**: Monitor response quality and user satisfaction

## Random Assignment Engine

### Testing and Analytics

The system includes comprehensive testing tools for the random assignment:

```typescript
// Test assignment distribution
const service = VersionAssignmentService.getInstance();

// Test with 1000 simulated assignments
service.testAssignmentDistribution('plato', 1000);

// Simulate actual user assignments
service.simulateUserAssignments('plato', 100);

// Get detailed analytics
const analytics = service.getAssignmentAnalytics('plato');
console.log(analytics);

// Get overall system health
const health = service.getAssignmentHealthCheck();
console.log(`System health score: ${health.healthScore}%`);

// Available in browser console
window.buchwurmVersionService.testAssignmentDistribution('plato', 1000);
```

### Assignment Features

- **Random Distribution**: True random assignment with configurable weights
- **Detailed Logging**: See exactly how each assignment is made
- **Analytics Tracking**: Monitor actual vs expected distribution
- **Health Monitoring**: Overall system performance metrics
- **Testing Tools**: Simulate assignments to verify distribution

## Version Management Best Practices

1. **Semantic Naming**: Use descriptive IDs (`base`, `enhanced`) not numbers
2. **Balanced Distribution**: Current 60/40 split provides good A/B testing data
3. **Gradual Rollouts**: Start with small percentages for new versions
4. **Monitor Metrics**: Track performance and user satisfaction
5. **Test Assignments**: Use built-in tools to verify distribution is working
6. **Document Changes**: Keep clear documentation of version differences
7. **Backward Compatibility**: Ensure version changes don't break existing conversations

## Future Enhancements

- **Dynamic Assignment**: Change version assignment based on user behavior
- **User Choice**: Allow users to manually select preferred versions
- **Contextual Versions**: Different versions for different conversation types
- **Multi-variate Testing**: Test combinations of features across versions
- **Version History**: Track version evolution and change impacts 