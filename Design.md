# PersonalDoc AI

## UI/UX Design Specification

## 1. Design Direction

The interface should feel like a focused AI workspace rather than a
generic dashboard.

Visual personality: - Clean. - Technical. - Calm. - Modern. -
Privacy-oriented. - Minimal visual noise.

The interface should make three things obvious: 1. What documents are
available. 2. What the user is asking. 3. Where the answer came from.

## 2. Theme

Use a dark-first interface.

### Background

-   Primary: near-black / charcoal.
-   Secondary surfaces: slightly lighter charcoal.
-   Cards: subtle elevation rather than heavy borders.

### Accent

Use a restrained electric mint/teal accent.

Suggested starting palette:

``` text
Background:       #0B0F0E
Surface:          #111817
Surface Elevated: #17201E
Border:           #26332F
Primary Text:     #F2F7F5
Secondary Text:   #9AA9A4
Accent:           #63E6BE
Accent Strong:    #2FD39A
Error:            #FF6B6B
Warning:          #FFD166
```

These are starting tokens, not rigid requirements.

## 3. Typography

Use a modern sans-serif.

Preferred: - Inter - Geist - system sans-serif fallback

Hierarchy: - Page title: 28-36px. - Section title: 18-22px. - Body:
14-16px. - Metadata: 12-13px.

Avoid excessive font weights.

## 4. Main Layout

``` text
┌──────────────────────────────────────────────────────────────┐
│ PersonalDoc AI                              ● Local / Ready  │
├───────────────┬──────────────────────────────────────────────┤
│               │                                              │
│ Documents     │                 Chat                         │
│               │                                              │
│ + Upload      │  User question                               │
│               │                                              │
│ All Documents │  Assistant answer                            │
│               │  ┌───────────────────────────────┐           │
│ report.pdf    │  │ Sources                       │           │
│ notes.pdf     │  │ report.pdf • p. 14            │           │
│ paper.pdf     │  └───────────────────────────────┘           │
│               │                                              │
│               │  ┌──────────────────────────────────────┐    │
│               │  │ Ask about your documents...          │    │
│               │  └──────────────────────────────────────┘    │
└───────────────┴──────────────────────────────────────────────┘
```

## 5. Navigation

Left sidebar: - All Documents - Recent - Chat

Bottom/sidebar status: - Local LLM status. - Vector database status.

Keep navigation compact.

## 6. Document Library

Each document row/card should show: - Filename. - File type. - Page
count if available. - Indexed status. - Last indexed time. - Actions.

Actions: - Open/chat. - Re-index. - Delete.

Use clear status indicators: - Processing. - Indexed. - Failed.

## 7. Upload Experience

Upload should support: - Drag and drop. - File picker. -
Progress/processing state.

After upload:

``` text
Uploading
   ↓
Extracting
   ↓
Creating embeddings
   ↓
Indexed
```

Avoid fake progress percentages. If exact progress is unavailable, use a
processing state instead.

## 8. Chat Experience

Messages should be visually distinct but not overly decorative.

Assistant messages should include: - Answer. - Source cards. - Optional
retrieval metadata in a developer/debug mode.

User messages should remain compact.

The input area should support: - Enter to send. - Shift+Enter for
newline. - Disabled state while appropriate.

## 9. Source Cards

A source card should contain:

``` text
REPORT.PDF
Page 14

"...relevant excerpt from the document..."

[Open source]
```

The source card should make citations feel like evidence, not footnotes
buried at the bottom.

## 10. Empty States

### No Documents

``` text
Your document library is empty.

Upload a PDF to start asking questions about
your documents locally.

[Upload document]
```

### No Chat

``` text
Ask your documents anything.

Try:
"What are the main findings?"
"Summarize the methodology."
"What does the report say about X?"
```

## 11. Error States

Errors should be human-readable.

Bad:

``` text
HTTP 500 Internal Server Error
```

Better:

``` text
We couldn't process this document.

The PDF may contain unsupported content.
Try another PDF or check the backend logs.
```

## 12. Responsive Behavior

Desktop: - Persistent sidebar. - Large chat workspace.

Tablet: - Narrow sidebar. - Flexible content width.

Mobile: - Collapsible navigation. - Full-width chat. - Source cards
stack vertically.

## 13. Accessibility

-   Keyboard navigable controls.
-   Visible focus states.
-   Sufficient text contrast.
-   Buttons with descriptive labels.
-   Do not rely on color alone for status.

## 14. Motion

Use subtle transitions: - Button hover. - Sidebar expansion. - Source
card reveal. - Upload state changes.

Avoid excessive animations during LLM generation.

## 15. Design Principle

The UI should communicate:

> "Your documents stay here. Ask them questions."

Privacy should be visible through product behavior and status
indicators, not through a wall of security copy.
