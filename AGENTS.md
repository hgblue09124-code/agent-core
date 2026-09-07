# AGENT CORE — ENGINEERING ULTIMATUM
## 1. NATIVE iOS IS THE PRODUCT
For iOS product work:
Swift / SwiftUI → Xcode → iOS App
Web is NOT an alternative implementation.
FORBIDDEN unless explicitly requested:
- HTML / React / Next.js
- WebView
- Web wrapper
- Vercel
- Web implementation of an iOS task
If the task says iOS, build native iOS.
## 2. PRODUCT SURFACES ARE SEPARATE
Agent Core
├── Core / Runtime / Memory / Actions
├── Native iOS User Workspace
├── Web / Preview surface
└── Developer Console
Never confuse these surfaces.
Web Preview may be a UX reference.
It is not the iOS implementation target.
## 3. CORE IS PROTECTED
UI work must not redesign:
- Runtime
- Memory
- Actions / Tools
- Agent logic
- Core contracts
Preferred flow:
Core
↓
Existing events / state
↓
Thin adapter
↓
Native iOS UI
Adapter before Core refactor.
## 4. USER WORKSPACE
Native iOS User Workspace should evolve the existing:
- Your Agent
- Orb
- Composer
into:
Conversation
Agent Status
Work Progress
Result
Actions
Composer
Use real Runtime state where available.
No fake Runtime, fake results, or duplicate systems.
## 5. TOKEN DISCIPLINE
Context is an engineering resource.
Agents MUST:
- read only relevant files
- follow the direct dependency path
- reuse existing code
- implement immediately
- build early
- fix only task-related failures
Agents MUST NOT:
- scan the whole repository unnecessarily
- write long analysis
- inspect unrelated history
- refactor unrelated code
- create duplicate architecture
- explore outside task scope
READ LESS. CHANGE LESS. SHIP FASTER.
## 6. SCOPE IS LAW
Before coding, determine:
TARGET
ALLOWED
FORBIDDEN
DONE
Do not expand scope.
If an unrelated issue is discovered:
REPORT IT. DO NOT FIX IT.
## 7. IMPLEMENTATION LOOP
Understand
→ Implement
→ Build
→ Fix
→ Verify
→ Commit
→ PR
Do not stop at analysis or prototype.
## 8. BUILD = AGENT VERIFICATION
For iOS:
Xcode build MUST PASS.
Relevant tests should pass.
The agent does NOT need to package/sign the IPA unless explicitly requested.
IPA installation and real-device testing are OWNER ACCEPTANCE, not the agent's default responsibility.
## 9. PR DISCIPLINE
One task → one focused PR.
PR must contain:
- relevant implementation
- relevant tests
- build result
- concise summary
No unrelated changes.
## 10. HARD STOP
When:
Correct platform
+ Feature implemented
+ Core preserved
+ Build PASS
+ Relevant tests PASS
+ PR clean
STOP.
Do not continue polishing, refactoring, or expanding scope.
# FINAL RULES
iOS task → Native iOS.
Web is not a substitute for iOS.
Core architecture is protected.
Reuse before create.
Token is a resource.
Scope is law.
Build PASS is agent verification.
IPA is owner acceptance.
DONE → STOP.
