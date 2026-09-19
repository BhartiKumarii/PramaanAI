# Network Graph Enhancement Plan

## Current State
- Basic identity cluster graph with entity types (PERSON, CHECKPOINT, DOCUMENT, VEHICLE, TRAVEL_EVENT)
- Generic node styling and connection labels
- No face recognition history visualization
- Limited person differentiation

## Required Enhancements

### 1. Person Node Differentiation
- **Face match status indicators**: New face, Previous face, Partial match
- **Confidence level rings**: High confidence (green), Medium (yellow), Low (red)
- **Biometric history badges**: Shows number of previous encounters

### 2. Enhanced Connection Types
- **Face Match Connections**: "FACE_VERIFIED", "FACE_SIMILAR", "FACE_NEW"
- **Document Connections**: "SAME_DOCUMENT", "LINKED_DOCUMENTS"
- **Travel History**: "PREVIOUS_CROSSING", "FREQUENT_ROUTE"
- **Identity Cluster**: "IDENTITY_MATCH", "SUSPECTED_ALIAS"

### 3. Temporal Indicators
- **Connection age**: Recent (solid line), Historical (dashed line)
- **Frequency badges**: Number of times same connection observed
- **Last seen timestamps**: When relationship was last confirmed

### 4. Interactive Features
- **Node selection**: Tap to highlight all related connections
- **Filter by relationship type**: Show only face matches, only documents, etc.
- **Zoom and pan**: For complex networks with many entities
- **Detail panel**: Shows full relationship history when node selected

## Implementation Plan

### Android App (IdentityClusterGraph.kt)
1. Add face match status to IdentityClusterMember model
2. Create different node styles for face match confidence levels
3. Add connection type enum with different line styles
4. Implement temporal indicators with color coding
5. Add detail panel for selected nodes

### Web Dashboard (NetworkGraphView.tsx)
1. Enhance ReactFlow node types with face match indicators
2. Add custom edge types for different relationship kinds
3. Implement filtering controls
4. Add timeline slider for temporal navigation
5. Create relationship detail sidebar

### Backend API
1. Extend identity graph response with face match confidence
2. Add relationship timestamps and frequency counts
3. Include biometric history summaries
4. Provide filtering endpoints for relationship types

## Visual Design Changes

### Person Nodes
- **New Face**: Green dot badge, solid green border
- **Previous Face**: Blue dot badge, blue border with frequency count
- **Partial Match**: Yellow dot badge, dashed yellow border
- **No Match**: Red dot badge, red border

### Connection Lines
- **Face Verified**: Thick green line with checkmark
- **Face Similar**: Medium blue line with percentage
- **Document Link**: Purple dashed line
- **Travel History**: Orange dotted line
- **Identity Cluster**: Red thick line with alert icon

### Mobile Optimizations
- Larger touch targets (28dp minimum)
- Haptic feedback on node selection
- Swipe gestures for filtering
- Pinch-to-zoom support
- Clear visual hierarchy for small screens

## Success Metrics
- Officers can quickly identify new vs. returning travelers
- Face match confidence is immediately visible
- Relationship history is accessible within 2 taps
- Complex identity clusters are readable on mobile screens
- Performance remains smooth with 20+ node graphs