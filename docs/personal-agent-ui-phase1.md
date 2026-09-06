# Personal Agent UI — Phase 1: Audit & Implementation Spec

## 1. Source of Truth

This document serves as the UI/UX Source of Truth and implementation blueprint for porting the **Personal Agent** concept (`personal-agent-ui.html`) to the native iOS SwiftUI application (`ios/AgentCoreIOS/`).

* **Primary Visual & Interaction Source of Truth:** `personal-agent-ui.html`
  * Defines the aesthetic, visual hierarchy, layout rules, component structures, color palette, typography, spacing, radius scale, ambient orb animation, and interaction states.
  * In any visual or interaction conflict between `personal-agent-ui.html` and current SwiftUI code, `personal-agent-ui.html` takes absolute precedence.
* **Architecture & Runtime Authority:** `ios/AgentCoreIOS/` (and underlying `Agent-Core` kernel contracts)
  * Visual alignment must **never** break or bypass the existing runtime architecture, `LocalAgentServiceProtocol` API contracts, policy authorization model (`PolicyEngine`), or state machine transitions (`AgentLoopState` / `AgentRuntime`).
  * UI state must be strictly derived from runtime models (`AgentStatus`, `AgentRunEvent`, `AgentRunResult`, `PermissionRequest`, `ActivityRecord`, `VaultSummary`, `ConnectionStatus`). The UI must **never** synthesize fake runtime state or bypass runtime authorization.

---

## 2. Current UI Inventory

The current native iOS application (`ios/AgentCoreIOS/`) is structured as a developer/inspector dashboard rather than a user-facing Personal Agent application. Below is the inventory of current UI code artifacts:

| Module / File | Scope / Responsibilities | Current Design Pattern |
| :--- | :--- | :--- |
| `App/AgentCoreIOSApp.swift` | Application entrypoint (`@main`), `AppTab` enum, `ExecutionLifecycleState`, `AgentAppViewModel`, `MainTabView`, and 7 tab views (`HomeView`, `AgentView`, `ActivityView`, `VaultView`, `ConnectionsView`, `SettingsView`, `ReviewView`). | Monolithic SwiftUI file with raw system colors (`secondarySystemBackground`, `Color.blue`), standard iOS list views, developer inspection cards, and PR #20 interactive review console. |
| `API/AgentAPIModels.swift` | Data models: `AgentRunResult`, `MemoryItem`, `MemoryResult`, `Capability`, `CapabilityResult`, `Experience`, `AgentHealth`, `AgentStatus`, `AgentEventPhase`, `AgentEventStatus`, `AgentRunEvent`, `PermissionRequest`, `ActivityFilter`, `ActivityRecord`, `VaultCategory`, `VaultSummary`, `ConnectionKind`, `ConnectionState`, `ConnectionStatus`. | Well-structured Codable models for runtime communications. Some UI views do not yet leverage all specialized models (e.g., `ConnectionsView` uses `Capability` directly instead of `ConnectionStatus`). |
| `API/LocalAgentService.swift` | Concrete implementation of `LocalAgentServiceProtocol` binding runtime, vault, memory, experience, checkpoint, and update manager. | Clean service boundary providing async methods for goal execution, streaming, memory, activity filtering, vault summary, and connection listing. |
| `Runtime/AgentRuntime.swift` | Swift runtime orchestrator executing goals, streaming `AgentRunEvent`s, enforcing policy authorization, managing checkpoints, and recording experiences. | Authoritative runtime state machine. |
| `Storage/` | `LocalVaultStore`, `LocalMemoryStore`, `LocalExperienceStore`, `LocalCheckpointStore`. | File-backed JSON persistence in `Application Support/AgentCore/`. |

---

## 3. Screen-by-Screen Audit

### Home

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Greeting ("Good evening / Your agent"), Notification Bell, Status Pill, On-Device Privacy Chip, Centered Glowing Orb, Docked Input Pill, Quick Actions, Current Task, Recent Activity. | Kernel Overview ("Personal Agent Local" banner, Status, Mode, Provider, Active Capabilities, Storage Path). Developer inspection dashboard. | Completely different focus. HTML is personal agent central hub; SwiftUI is a system status dashboard. | Reconstruct Home screen layout around Orb, Agent Status Card, Docked Input Pill, Quick Actions grid, Active Task card, and Recent Activity list. | **P0** |
| **Layout** | Vertical scroll view, 16pt card gaps, centered orb block (118x118px), docked input pill at card bottom, 2-column quick action grid. | Single vertical `VStack` with standard `Form`/`List` style inset cards. | Lacks visual anchors, orb centering, and horizontal quick action grid layout. | Implement `AgentStatusCard` with custom ambient orb, status pill top bar, and integrated `InputPill` composer. | **P0** |
| **Components** | `StatusPill`, `PrivacyChip`, `AgentOrb`, `InputPill`, `QuickActionCard`, `CurrentTaskCard` (with progress bar), `ActivityRow`. | Raw `HeaderBanner` and `StatusRow` components displaying debug text strings. | Missing all specialized personal agent visual components. | Build reusable shared components: `AgentOrb`, `StatusPill`, `InputPill`, `QuickActionCard`, `CurrentTaskCard`. | **P0** |
| **Typography** | Display 26pt bold, Title 17pt, Body 15pt, Secondary 13pt, Caption 12pt/11pt. | Standard SwiftUI `.font(.title)`, `.font(.headline)`, `.font(.caption)`. | System default font scale does not match refined HTML typography rhythm. | Apply exact typographic scale using `AgentFont` design tokens. | **P1** |
| **Colors** | Background `#0A0A0D`, Surface `#141417`, Hairline border `rgba(255,255,255,0.08)`, Accent `#7C8CFF`, Conic gradient orb. | System `secondarySystemBackground`, system `.blue`, `.green`, `.purple`. | Default iOS system colors used instead of dark palette and accent color. | Apply dark design token color palette (`AgentColor`). | **P1** |
| **Interactions** | Tap input pill to compose/speak, tap Quick Action to trigger task, tap "See all" to jump to Activity. | Read-only static text labels. | No direct input action from Home. | Bind `InputPill` submit action to goal execution and navigation. | **P0** |

---

### Agent / Execute

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Screen title ("Execute"), Live status pill ("Thinking"), Task Goal Card, Step Progress List (completed steps with checkmark, active step with mini orb indicator), Progress bar, Cancel/Retry action bar. | "Interactive Execution" header, raw `TextField`, 4 row buttons ("Run Task", "Run Prompt", "Cancel", "Clear"), Lifecycle badge, JSON-like Run Result card, Error payload card. | SwiftUI presents a developer test form rather than an active task execution console. | Redesign `AgentView` as live execution observer: Task Card, Step Stream List, Progress Bar, and Control Bar (Cancel / Retry). | **P0** |
| **Layout** | Card-based vertical stack with sticky bottom button bar (`Cancel`, `Retry`). | Form layout with horizontal button wrap and scrollable result cards. | Control buttons are placed above status outputs rather than anchored at the bottom. | Anchor `Cancel` and `Retry` buttons at screen bottom; display active task details at top. | **P1** |
| **Components** | `TaskSummaryCard`, `ExecutionStepRow` (completed icon, active orb, pending dot), `ProgressBar`, `ActionButton`. | Standard `TextField`, `Button`, `StatusBadge`, `DetailRow`. | Missing step-by-step progress list rows with phase-specific icons and animation. | Implement `ExecutionStepRow` and `ProgressBar` bound to `AgentRunEvent` stream. | **P0** |
| **States** | Thinking (breathing orb), Running (progress bar fill), Completed (success tint), Failed (error message + Retry action). | Lifecycle enum text badges (`Preparing`, `Running`, `Completed`, `Failed`, `Cancelled`). | Lack of visual step transitions and inline error recovery interface. | Map `AgentEventPhase` and `AgentEventStatus` directly to step row states and progress calculations. | **P0** |

---

### Activity

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Screen title ("Activity"), Segmented Filter (`All`, `Success`, `Failed`), Timeline list card containing activity rows with icon tiles (Check, X), title, timestamp, and duration/status message. | Screen title ("Activity"), Section header "Execution & Event Logs (N)", standard SwiftUI `List` rows with `StatusBadge` and debug text. | Missing segmented filter control; layout uses standard iOS section headers instead of unified card list. | Add top `SegmentedPicker` (`All`, `Success`, `Failed`), group activity items inside elevated surface cards using `ActivityRow`. | **P1** |
| **Layout** | Compact segmented control below title, continuous list card with hairline row dividers (`list-item`). | Standard grouped `List` style with heavy default margins and plain text rows. | Visual density too low; row layout lacks square icon tiles. | Use tight list row spacing, 28x28px `IconTile` for status (green checkmark for success, red X for fail). | **P1** |
| **Data Source**| `listActivity(filter: filter)` returning `ActivityRecord` items. | `service.listActivity(filter: .all)` returning `ActivityRecord` items. | Filter segment state in UI is not bound to `ActivityFilter`. | Bind `SegmentedPicker` selection directly to `viewModel.filter` and `service.listActivity(filter:)`. | **P0** |

---

### Vault

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Title ("Vault"), "Private" on-device chip, Search Input Pill ("Search memory"), 2-column Category Grid (`Documents 128 items`, `Notes 54 items`), Context summary card ("Context the agent remembers"). | Title ("Vault"), `List` with two sections: "Stored Personal Memories" and "Stored Experiences". | Completely missing category grid cards, search input pill, and context overview card. | Add "Private" chip, `SearchPill`, 2-column `CategoryCard` grid (`Documents`, `Notes`, `Preferences`), and `RememberedContextCard`. | **P1** |
| **Layout** | Top search pill, 2x2 grid for memory categories, elevated card for remembered context summary. | Plain vertical `List` with text rows `[key]: value`. | List view shows raw key-value pairs without categorization or memory search. | Implement top search bar filter and category cards using `VaultSummary` metrics. | **P1** |
| **Data Source**| `VaultSummary`, `MemoryItem` categorized into `VaultCategory`. | Raw `memories` array and `experiences` array. | `VaultSummary` model is present in `AgentAPIModels.swift` but ignored in current `VaultView`. | Call `service.vaultSummary()` and map vault categories to category grid cards. | **P0** |

---

### Connections

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Title ("Connections"), list of capability connections showing icon tile, connection name, location text ("On-device" vs "Remote"), state chip (`Local` green chip vs `Remote` neutral chip), and inline action ("Connect"). | Title ("Connections"), `List` of `Capability` items with version, readOnly badge, and approval requirement badge. | Shows raw developer capability flags (`READ ONLY`, `APPROVAL REQ`) rather than user-understandable connection status (`Local` vs `Remote`). | Transform item layout to `ConnectionRow` displaying `ConnectionKind` (`Local`/`Remote`), connection state, and action link. | **P1** |
| **Layout** | Single list card with hairline dividers, 28x28px icon tiles, badge chips right-aligned. | Standard SwiftUI `List` with multi-badge stack. | Lacks visual distinction between local capabilities and remote service integrations. | Implement explicit `Local` vs `Remote` badge styling (`Chip.local` green vs neutral `Chip.remote`). | **P1** |
| **Data Source**| `service.listConnections()` returning `ConnectionStatus` items. | `service.listCapabilities()` returning `Capability` items. | `ConnectionStatus` model exists in `AgentAPIModels.swift` but current UI binds `Capability` directly. | Update `ConnectionsView` to bind `viewModel.connections` populated via `service.listConnections()`. | **P0** |

---

### Settings

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Title ("Settings"), Grouped card list: Background execution toggle, Privacy mode toggle, Storage info, Appearance, About. | Title ("Settings"), GitHub Data Update report, Installed Data Version, Local Environment debug details (Storage Directory, Planner Provider). | Current SwiftUI shows build/data update diagnostic telemetry rather than user settings. | Reorganize `SettingsView` into clean native grouped lists: User Toggles, Storage usage, Appearance selector, About, and Data Update Status. | **P1** |
| **Layout** | Single card containing native list items with trailing toggle switches and chevron indicators. | Standard `DetailRow` text stack. | Lacks custom dark card wrapper and interactive toggle controls. | Wrap settings rows in `SettingsCard` using `Toggle` switches and trailing chevron icons. | **P1** |

---

### Review

| Audit Dimension | HTML Concept (`personal-agent-ui.html`) | Current SwiftUI (`AgentCoreIOSApp.swift`) | Gap | Required Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy** | Not present in 5-tab HTML concept. (Review tab was added in SwiftUI for PR #20 interactive verification console). | Tab 7: "Interactive Review Console", Review Dashboard (6 status cells), Agent Execution Test, Memory/Vault Test, Error Handling Scenarios, Activity Sync Check, 10 Automated Review Checks, Architecture Validation Banner. | Review tab exists only in SwiftUI as a developer testing tool. | Keep `ReviewView` functional for developer testing, but align its styling with shared design tokens (`AgentColor`, `AgentCard`). Ensure it does not clutter primary user navigation. | **P2** |

---

## 4. Design Tokens

Below are the exact design tokens extracted from `personal-agent-ui.html`. These values must be implemented as static extensions on `Color`, `Font`, `CGFloat`, and `EdgeInsets` in SwiftUI (`AgentDesignTokens.swift`).

### Colors (`AgentColor`)

| Token Name | Hex / RGBA | Value | Usage / Purpose |
| :--- | :--- | :--- | :--- |
| `background0` | `#020203` | `Color(hex: 0x020203)` | Deepest background / gradient base |
| `background1` | `#0A0A0D` | `Color(hex: 0x0A0A0D)` | Primary screen background (`var(--bg-1)`) |
| `background2` | `#141417` | `Color(hex: 0x141417)` | Card surface background (`var(--bg-2)`) |
| `background3` | `#1D1D22` | `Color(hex: 0x1D1D22)` | Elevated tile / button background (`var(--bg-3)`) |
| `background4` | `#26262C` | `Color(hex: 0x26262C)` | Segment/progress fill background (`var(--bg-4)`) |
| `hairline` | `rgba(255,255,255,0.08)` | `Color.white.opacity(0.08)` | Standard card/divider border (`var(--hair)`) |
| `hairlineStrong` | `rgba(255,255,255,0.14)` | `Color.white.opacity(0.14)` | Focused/input border (`var(--hair-strong)`) |
| `textPrimary` | `#F5F5F7` | `Color(hex: 0xF5F5F7)` | Headings, primary text (`var(--text-1)`) |
| `textSecondary` | `rgba(245,245,247,0.62)` | `Color(hex: 0xF5F5F7).opacity(0.62)` | Subtitles, descriptions (`var(--text-2)`) |
| `textMuted` | `rgba(245,245,247,0.36)` | `Color(hex: 0xF5F5F7).opacity(0.36)` | Captions, placeholders (`var(--text-3)`) |
| `accent` | `#7C8CFF` | `Color(hex: 0x7C8CFF)` | Primary restrained accent, active tab |
| `accentDim` | `rgba(124,140,255,0.14)` | `Color(hex: 0x7C8CFF).opacity(0.14)` | Thinking status background, accent tiles |
| `violet` | `#B18CFF` | `Color(hex: 0xB18CFF)` | Orb gradient component |
| `cyan` | `#7FE0E0` | `Color(hex: 0x7FE0E0)` | Orb gradient component |
| `success` | `#3DD68C` | `Color(hex: 0x3DD68C)` | Ready status, completed checkmarks |
| `successDim` | `rgba(61,214,140,0.14)` | `Color(hex: 0x3DD68C).opacity(0.14)` | Ready status background, local chip |
| `warning` | `#F5B84D` | `Color(hex: 0xF5B84D)` | Running status, warnings |
| `warningDim` | `rgba(245,184,77,0.14)` | `Color(hex: 0xF5B84D).opacity(0.14)` | Running status background |
| `danger` | `#F5716B` | `Color(hex: 0xF5716B)` | Failed status, error indicators |
| `dangerDim` | `rgba(245,113,107,0.14)` | `Color(hex: 0xF5716B).opacity(0.14)` | Failed status background |
| `offline` | `#8B8B92` | `Color(hex: 0x8B8B92)` | Offline status, disabled controls |

---

### Typography (`AgentFont`)

Typography follows system SF Pro Display / SF Pro Text with strict font weights (500 Medium, 600 Semi-bold):

| Style Name | Font Family | Size (pt) | Weight | Line Height / Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `display` | SF Pro Display | 34pt | 600 SemiBold | -0.01em | Large headers ("Your agent") |
| `h1` | SF Pro Display | 26pt | 600 SemiBold | -0.01em | Screen titles |
| `title` | SF Pro Text | 22pt | 600 SemiBold | 1.2 | Section titles |
| `headline` | SF Pro Text | 17pt | 600 SemiBold | 1.25 | Card headers, primary items |
| `subheadline` | SF Pro Text | 14.5pt | 600 SemiBold | 1.3 | Task titles, quick action text |
| `body` | SF Pro Text | 15pt | 500 Medium | 1.4 | Primary body copy |
| `secondary` | SF Pro Text | 13pt | 400 Regular | 1.4 | Secondary descriptions, subtitles |
| `caption` | SF Pro Text | 12pt | 500 Medium | 1.3 | Metadata, section eyebrow labels |
| `captionSmall` | SF Pro Text | 11pt | 500 Medium | 1.2 | Chips, status pills, list subtext |
| `mono` | Roboto Mono / SF Mono | 12pt | 400 Regular | 1.2 | Timestamps, durations, code paths |

---

### Spacing & Grid (`AgentSpacing`)

An 8pt spacing scale governs layout padding and element relationships:

| Token | Value (pt) | Usage |
| :--- | :--- | :--- |
| `xs` | 4pt | Icon-to-text gap, status dot margin |
| `sm` | 8pt | Compact button padding, inner card element gap |
| `md` | 12pt | Standard row padding, card internal gaps |
| `lg` | 16pt | Page edge margin, card padding, section gap |
| `xl` | 20pt | Screen edge padding, hero card inner padding |
| `xxl` | 24pt | Section top/bottom margins |
| `xxxl` | 32pt | Major component separation |

---

### Corner Radius (`AgentRadius`)

| Token | Value (pt) | Usage |
| :--- | :--- | :--- |
| `small` | 8pt | Chips, small badge pills |
| `tile` | 12pt | Icon tile background (38x38px) |
| `segmented` | 14pt | Segmented picker control background |
| `card` | 20pt | Standard surface cards (`var(--bg-2)`) |
| `button` | 24pt | Input pill, action buttons |
| `pill` | 100pt | Full rounded status pills (`Pill.ready`, `Pill.thinking`) |

---

### Borders & Dividers (`AgentBorder`)

| Token | Width (pt) | Color | Usage |
| :--- | :--- | :--- | :--- |
| `hairline` | 1.0pt | `Color.white.opacity(0.08)` | Card borders, list dividers |
| `hairlineStrong` | 1.0pt | `Color.white.opacity(0.14)` | Input pill outline, active card outline |

---

### Interaction States

| State | Visual Representation | Motion / Animation |
| :--- | :--- | :--- |
| **Ready / Idle** | Green status pill (`#3DD68C`), static glowing core dot in orb. | Static, no rotation. |
| **Thinking** | Accent status pill (`#7C8CFF`), conic gradient orb. | Continuous 5s linear 360° rotation (`spin`). |
| **Running** | Warning status pill (`#F5B84D`), progress bar filled. | Pulsing status dot (1.4s infinite ease-in-out). |
| **Completed** | Success icon tile, green background tint (`rgba(61,214,140,0.14)`). | Settles for 2s before returning to Idle. |
| **Failed** | Danger icon tile (`#F5716B`), red background tint, Retry button. | Static alert highlight. |
| **Offline** | Neutral offline pill (`#8B8B92`), cloud-off icon tile. | Static neutral state. |
| **Pressed** | 0.96 scale transform, opacity `0.8` on press. | Quick 0.15s ease-out animation. |
| **Disabled** | Opacity `0.4`, user interaction disabled. | None. |

---

## 5. Shared Component System

To eliminate custom ad-hoc styling across screens, Phase 2 will implement a centralized shared component library (`ios/AgentCoreIOS/Components/`).

```
Components/
├── AgentOrbView.swift          # Central glowing ambient agent orb
├── StatusPillView.swift        # Ready / Thinking / Running / Offline pill
├── PrivacyChipView.swift       # On-device / Private shield chip
├── InputPillView.swift         # Docked task composer input pill
├── QuickActionCard.swift       # 2-column task / memory quick trigger card
├── CurrentTaskCard.swift       # Active running task card with progress bar
├── IconTileView.swift          # 38x38px and 28x28px status icon tiles
├── ActivityRowView.swift       # Standardized activity timeline item
├── StepProgressRow.swift       # Live execution step row with status icons
├── ConnectionRowView.swift     # Capability connection status item
├── VaultCategoryCard.swift     # 2-column memory category item
└── SegmentedPickerView.swift   # Custom dark segmented filter control
```

### Component Specifications

#### 1. `AgentOrbView`
* **Purpose:** Primary visual representation of the agent's active cognitive state.
* **Visual Structure:** 118x118px circular container with a multi-stop conic gradient (`#4B5BE0` → `#7C8CFF` → `#B18CFF` → `#7FE0E0` → `#4B5BE0`), semi-opaque inner mask, and centered glowing white core dot (14x14px with `#7C8CFF` drop shadow).
* **States:**
  * `idle`: Static gradient orb.
  * `thinking`: Continuous 5s rotation animation (`.rotationEffect(.degrees(isSpinning ? 360 : 0))`).
  * `mini`: Scaled-down 14x14px version for active step row indicator.
* **Inputs/Data:** `status: AgentStatus`
* **Reuse Locations:** `HomeView`, `AgentView` (mini step indicator).

#### 2. `StatusPillView`
* **Purpose:** Displays high-level agent operational state.
* **Visual Structure:** Capsule shape with 6x6px dot indicator and text label.
* **States:**
  * `ready`: Background `successDim`, text/dot `success` ("Ready").
  * `thinking`: Background `accentDim`, text/dot `accent` ("Thinking", pulsing dot).
  * `running`: Background `warningDim`, text/dot `warning` ("Running", pulsing dot).
  * `offline`: Background `rgba(139,139,146,0.16)`, text/dot `offline` ("Offline").
* **Inputs/Data:** `status: AgentStatus`
* **Reuse Locations:** `HomeView`, `AgentView`, `ReviewView`.

#### 3. `InputPillView`
* **Purpose:** Primary text and voice task entry point.
* **Visual Structure:** 52pt height pill container, `#141417` surface, `hairlineStrong` border, microphone icon left, text placeholder center, submit arrow button right.
* **States:** Normal, Focused (brighter border), Disabled.
* **Inputs/Data:** `@Binding text: String`, `onSubmit: () -> Void`.
* **Reuse Locations:** `HomeView`, `VaultView` (search mode).

#### 4. `CurrentTaskCard`
* **Purpose:** Displays real-time progress of an ongoing agent task on Home.
* **Visual Structure:** Elevated card (`#141417`), top header row with "Current task" caption and "Running" pill, middle row with warning icon tile, task title, subtext, and bottom progress bar (`ProgressBarView`).
* **Inputs/Data:** `goal: String`, `subtext: String`, `progress: Double`.
* **Reuse Locations:** `HomeView`.

---

## 6. Runtime → UI Data Mapping

To preserve strict runtime integrity, all UI components must bind directly to `LocalAgentServiceProtocol` methods and Codable models without fake or synthetic state.

| UI State / Component | Source | API / Model | Current Implementation | Gap & Fix Requirement |
| :--- | :--- | :--- | :--- | :--- |
| **Agent Status Pill / Orb** | `LocalAgentService` | `AgentStatus` (`READY`, `THINKING`, `RUNNING`, `OFFLINE`) | Derived from `executionState` enum in `AgentAppViewModel`. | Call `service.currentAgentStatus()` or subscribe to status stream. Fix: ViewModel publishes `agentStatus: AgentStatus`. |
| **Active Task Progress** | `AgentRuntime` | `AgentRunEvent` (`phase`, `status`, `summary`) | Standard `Task` wrapper in ViewModel updating `executionState`. | Stream `runStreaming()` events into `AgentRunEvent` list. Fix: Pass live event payload to `CurrentTaskCard` and `ExecutionStepRow`. |
| **Activity Timeline** | `LocalExperienceStore` | `ActivityRecord`, `ActivityFilter` (`ALL`, `SUCCESS`, `FAILED`) | `service.listActivity(filter: .all)` | Add UI filter binding (`viewModel.selectedFilter`) to `service.listActivity(filter: selectedFilter)`. |
| **Vault Categories & Memory** | `LocalVaultStore` / `LocalMemoryStore` | `VaultSummary`, `MemoryItem`, `VaultCategory` | `service.retrieve(query: "")` returning flat array. | Call `service.vaultSummary()` to retrieve category counts and total storage bytes for `VaultCategoryCard` grid. |
| **Connection Capabilities** | Capability Registry | `ConnectionStatus` (`capabilityId`, `name`, `kind`, `state`) | `service.listCapabilities()` returning `Capability`. | Call `service.listConnections()` to populate `ConnectionStatus` array with explicit `LOCAL` vs `REMOTE` distinction. |
| **Permission Request Card** | `PolicyEngine` | `PermissionRequest` (`requestId`, `runId`, `capabilityId`, `reason`) | SwiftUI `alert` dialog. | Wrap unapproved capability requests into `PermissionCard` component in `AgentView` and `ReviewView`. |

---

## 7. Navigation Audit

### Current Navigation Structure
* **Pattern:** Bottom `TabView` with 7 tabs (`Home`, `Agent`, `Activity`, `Vault`, `Connections`, `Settings`, `Review`).
* **Implementation:** `MainTabView` in `AgentCoreIOSApp.swift` using standard system SF Symbols (`house.fill`, `cpu.fill`, `list.bullet.rectangle.fill`, `lock.shield.fill`, `network`, `gearshape.fill`, `checkmark.seal.fill`).

### Target Navigation Structure (from HTML Concept)
* **Pattern:** Floating glassmorphic bottom tab bar with 5 primary tabs (`Home`, `Agent`, `Activity`, `Vault`, `Settings`).
* **Styling:** Surface `rgba(20,20,23,0.72)` with blur backdrop (`backdrop-filter: blur(20px)`), hairline top border, custom SVG linear icons (`i-home`, `i-bolt`, `i-activity`, `i-vault`, `i-gear`), and active indicator dot.

### Navigation Comparison & Gap Analysis

| Dimension | Current SwiftUI | Target (HTML Concept) | Gap / Recommendation |
| :--- | :--- | :--- | :--- |
| **Tab Count** | 7 tabs (includes `Connections` and `Review`). | 5 tabs (`Home`, `Agent`, `Activity`, `Vault`, `Settings`). | Connections and Review tabs inflate the tab bar. **Recommendation:** For Phase 2, integrate Connections under Settings or Vault, and restrict Review tab to Debug/Developer builds using `#if DEBUG`. Keep 5 tabs in primary user tab bar. |
| **Tab Order** | Home, Agent, Activity, Vault, Connections, Settings, Review. | Home, Agent, Activity, Vault, Settings. | Order matches except extra tabs. |
| **Bar Aesthetic** | Default native white/gray iOS tab bar background. | Glassmorphic dark tab bar (`rgba(20,20,23,0.72)`) with active accent dot. | Tab bar styling needs dark glassmorphic container and custom active dot indicator. |

---

## 8. Personal Agent UX Audit

A core directive of Phase 1 is evaluating the application against the guiding philosophy: **"This is a Personal Agent app, not a developer dashboard."**

| UX Audit Question | Assessment of Current SwiftUI App | Required Design Paradigm Shift |
| :--- | :--- | :--- |
| **Is Home really the center of the agent?** | **NO.** Home displays technical kernel metrics ("Provider", "Storage Path", "Mode") that look like an admin status panel. | Home must present the **Agent Orb**, current state pill, quick action triggers, and active task progress. Technical diagnostic paths belong in Settings or Review. |
| **Can the user see what the agent is doing?** | **PARTIALLY.** Running tasks show text output, but lack step-by-step cognitive progress visualization. | Implement live streaming step progress rows (`Read inbox` → `Grouped by sender` → `Drafting reply 3 of 7...`) in `AgentView` and `HomeView`. |
| **Is asking the agent a task the primary interaction?** | **NO.** In current SwiftUI, the user must navigate to Tab 2 (`Agent`) and fill out a debug form text box. | The `InputPill` composer must be prominently docked on `HomeView` so the user can immediately type or speak a task upon launching the app. |
| **Does Activity feel like agent action history?** | **NO.** Activity items look like developer debug log entries (`[KRUN-90865]: COMPLETED`). | Activity rows must highlight user-centric task summaries ("Summarized weekly emails", "Backed up notes") with execution duration and status badges. |
| **Does Vault feel like agent memory?** | **NO.** Vault displays raw JSON arrays `[key]: value`. | Vault must feel like personal memory storage with clear category folders ("Documents", "Notes", "Preferences") and a summary of remembered user context. |
| **Does Connections highlight capability limits?** | **NO.** Shows developer flag lists (`READ ONLY`, `APPROVAL REQ`). | Connections must clearly distinguish between **On-device Local capabilities** (always available, private) and **Remote Integrations** (calendar, email requiring user authorization). |

---

## 9. Accessibility & Native iOS Considerations

When porting `personal-agent-ui.html` to native iOS SwiftUI, the following platform guidelines must be implemented:

1. **Dynamic Type Support:**
   * Text sizes must use `@ScaledMetric` or relative SwiftUI text styles (`.font(.custom(..., relativeTo: .body))`) so that font sizes scale gracefully when users adjust iOS text size accessibility settings.
2. **Touch Targets:**
   * All interactive buttons, input pills, quick action cards, and tab items must maintain a minimum touch target area of **44x44 pt** per Apple Human Interface Guidelines (HIG).
3. **VoiceOver Accessibility Labels:**
   * `AgentOrbView`: Accessible label `"Agent Status: Ready"` / `"Agent Status: Thinking"`.
   * `StatusPillView`: Accessibility trait `.isHeader` or `.updatesFrequently`.
   * `InputPillView`: Accessibility prompt `"Ask your agent to do something, text field"`.
4. **Safe Area & Keyboard Avoidance:**
   * Bottom tab bar and docked input pill must respect `safeAreaInsets.bottom` (home indicator region).
   * Scrolling views must use `.scrollDismissesKeyboard(.interactively)` to ensure input fields remain usable during task composition.
5. **Reduced Motion:**
   * Respect `@Environment(\.accessibilityReduceMotion)`. When enabled, disable the continuous spinning rotation of `AgentOrbView` and replace it with a subtle pulse or static accent glow.

---

## 10. Gap Analysis & Runtime Integrity Checks

During the audit of `ios/AgentCoreIOS/`, several implementation inconsistencies and runtime integrity risks were identified. **None of these shall be modified in Phase 1**, but are documented here for resolution during Phase 2:

### Identified Runtime Integrity & UI Issues

```
1. FILE: ios/AgentCoreIOS/App/AgentCoreIOSApp.swift
   FUNCTION: ConnectionsView.body
   CURRENT BEHAVIOR: Lists `viewModel.capabilities` directly using `Capability` model instead of `ConnectionStatus`.
   WHY IT IS WRONG: Bypasses `LocalAgentServiceProtocol.listConnections()`, ignoring `ConnectionKind` (LOCAL vs REMOTE) and `ConnectionState`.
   TARGET BEHAVIOR: Bind `ConnectionsView` to `viewModel.connections` fetched via `service.listConnections()`.

2. FILE: ios/AgentCoreIOS/App/AgentCoreIOSApp.swift
   FUNCTION: HomeView.body
   CURRENT BEHAVIOR: Renders static debug text ("Kernel Overview", "Storage Path") inside `StatusRow`.
   WHY IT IS WRONG: Treats Home as a developer status console rather than the personal agent interaction center.
   TARGET BEHAVIOR: Replace debug stack with `AgentStatusCard`, `AgentOrbView`, `InputPillView`, `QuickActionCard` grid, and `CurrentTaskCard`.

3. FILE: ios/AgentCoreIOS/App/AgentCoreIOSApp.swift
   FUNCTION: AgentAppViewModel.init
   CURRENT BEHAVIOR: Hardcodes default task string `"Remember that my favorite color is blue."` and hardcodes PR #20 review checks in view model state.
   WHY IT IS WRONG: Introduces hardcoded test goals and non-production testing data into default application state.
   TARGET BEHAVIOR: Initialize empty default state for production views; isolate review/test state strictly inside `ReviewView`.

4. FILE: ios/AgentCoreIOS/API/AgentAPIModels.swift vs Storage Models
   CURRENT BEHAVIOR: `ActivityRecord` defines computed UI string formatters (`task`, `state`, `timestamp`, `duration`, `resultOrError`).
   WHY IT IS WRONG: Duplicates fields between `Experience` and `ActivityRecord`.
   TARGET BEHAVIOR: Standardize `ActivityRecord` conversion directly from `Experience` or runtime `AgentRunResult` in `LocalAgentService`.
```

---

## 11. Implementation Priority

Phase 2 implementation must proceed in the following prioritized sequence:

| Priority Order | Target Scope | Key Deliverables | Dependency |
| :---: | :--- | :--- | :--- |
| **1** | **Shared Design Tokens** | Implement `AgentDesignTokens.swift` (`AgentColor`, `AgentFont`, `AgentSpacing`, `AgentRadius`). | None |
| **2** | **Shared Components** | Implement `AgentOrbView`, `StatusPillView`, `PrivacyChipView`, `InputPillView`, `QuickActionCard`, `CurrentTaskCard`, `IconTileView`, `ActivityRowView`. | Priority 1 |
| **3** | **Home View** | Reconstruct `HomeView` layout around Orb, Status Card, Input Pill, Quick Actions, and Active Task card. | Priority 2 |
| **4** | **Agent / Execute View** | Redesign `AgentView` as step-by-step task execution and progress stream. | Priority 2, 3 |
| **5** | **Activity View** | Refactor `ActivityView` with segmented filter (`All`, `Success`, `Failed`) and card list rows. | Priority 2 |
| **6** | **Vault View** | Upgrade `VaultView` with `SearchPill`, 2-column `CategoryCard` grid, and context overview card. | Priority 2 |
| **7** | **Connections View** | Refactor `ConnectionsView` to bind `ConnectionStatus` (`LOCAL` vs `REMOTE` chips). | Priority 2 |
| **8** | **Settings View** | Clean up `SettingsView` into native grouped cards for user toggles and system info. | Priority 2 |
| **9** | **Review View Refactoring** | Ensure developer `ReviewView` uses shared tokens without affecting primary 5-tab user navigation. | Priority 1–8 |
| **10** | **Runtime / UI Integration Audit** | Eliminate hardcoded state, bind all view models to `LocalAgentServiceProtocol` methods. | Priority 3–9 |
| **11** | **Device Verification** | Validate UI layouts across iPhone screen sizes, dark mode, VoiceOver, and XCTest suite. | Priority 10 |

---

## 12. Phase 2 Implementation Plan

Phase 2 will implement the native SwiftUI UI overhaul step-by-step based on this blueprint.

### Execution Steps for Phase 2

1. **Create Component & Design System Directory:**
   * Create `ios/AgentCoreIOS/Components/` and `ios/AgentCoreIOS/Theme/`.
   * Create `AgentDesignTokens.swift` containing `AgentColor`, `AgentFont`, `AgentSpacing`, `AgentRadius`, `AgentBorder`.
2. **Implement Core Reusable UI Components:**
   * Implement `AgentOrbView.swift` with smooth 360° conic rotation animation and `accessibilityReduceMotion` support.
   * Implement `StatusPillView.swift`, `PrivacyChipView.swift`, `InputPillView.swift`.
   * Implement `QuickActionCard.swift`, `CurrentTaskCard.swift`, `ProgressBarView.swift`.
3. **Refactor Screen Views:**
   * **Home:** Rebuild `HomeView.swift` adhering to Section 3 spec.
   * **Agent:** Rebuild `AgentView.swift` with live step progress list.
   * **Activity:** Rebuild `ActivityView.swift` with `SegmentedPickerView` and `ActivityRowView`.
   * **Vault:** Rebuild `VaultView.swift` with category grid cards and memory search bar.
   * **Connections:** Rebuild `ConnectionsView.swift` bound to `service.listConnections()`.
   * **Settings:** Rebuild `SettingsView.swift` as native grouped settings card.
4. **Clean View Models & Remove Synthetic State:**
   * Remove hardcoded default test goals and debug strings from `AgentAppViewModel`.
   * Isolate PR #20 review checks to `ReviewView`.
5. **Run Verification & Test Suite:**
   * Execute XCTest suite (`xcodebuild test -scheme AgentCoreIOS`) and Python unit tests (`python3 -m unittest discover -s tests`).
   * Verify zero regressions in core runtime or capability integration.

---

## 13. Open Questions & Ambiguities

During Phase 1 reverse-engineering and audit, the following architectural ambiguities were noted. They are recorded here for stakeholder alignment without altering core runtime contracts:

1. **Tab Bar Count vs. Review Tab:**
   * *HTML Concept:* Defines 5 primary tabs (`Home`, `Agent`, `Activity`, `Vault`, `Settings`).
   * *Current SwiftUI:* Contains 7 tabs (adds `Connections` and `Review`).
   * *Resolution:* Keep 5 primary tabs in the main user tab bar (`Home`, `Agent`, `Activity`, `Vault`, `Settings`). Connections can be accessed via Vault or Settings, while Review remains a developer debug tab accessible via Settings or debug builds.
2. **Orb Animation Overhead on Lower-End iOS Devices:**
   * Continuous 360° rotation on complex conic gradients can consume GPU cycles on older iOS hardware.
   * *Resolution:* Use lightweight SwiftUI `DrawingGroup` (Metal rendering) for `AgentOrbView` and respect iOS `accessibilityReduceMotion`.
3. **Light Mode Support:**
   * *HTML Concept:* Exclusively specifies dark mode (`#0A0A0D` background, white hairline borders).
   * *Resolution:* Personal Agent UI will be dark-first / dark-preferred. If running on an iOS device set to Light Mode, card surfaces will maintain high contrast while adhering to the dark aesthetic, or support a dedicated dark theme toggle in Settings.
