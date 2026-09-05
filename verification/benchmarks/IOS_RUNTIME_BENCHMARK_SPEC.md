# iOS Native Local Runtime Benchmark Specification v0.1

**Target Architecture**: Native Full-Local Personal Agent on iOS / iPhone
**Target Repository**: `Agent-Core` (`hgblue09124-code/agent-core`)
**Purpose**: Specification of metrics, benchmark targets, and test methodologies for future native iOS runtime benchmarking.

---

## 1. Required Benchmark Metrics

The future native iOS runtime MUST measure and report performance across the following 13 core metrics:

| Metric Name | Benchmark Target Description | Target Budget (iPhone 15/16 Class) |
|-------------|------------------------------|-----------------------------------|
| **Cold Start** | Latency from iOS process spawn to kernel service readiness. | < 250 ms |
| **Agent Initialization** | `Agent.__init__()` and subsystem binding latency. | < 50 ms |
| **Memory Read/Write Latency** | `remember()` and `retrieve()` operations on local store. | < 5 ms per op |
| **Vault Read/Write Latency** | `store_context()` and `retrieve_context()` on vault. | < 2 ms per op |
| **`Agent.run` E2E Latency** | Full orchestration loop duration (local mock planner). | < 300 ms |
| **Capability Discovery** | `list_specs()` capability registry query latency. | < 1 ms |
| **Capability Execution** | On-device local capability execution latency. | < 100 ms |
| **Policy Authorization** | `PolicyEngine.authorize_capability()` check latency. | < 0.1 ms |
| **Persistence Reload** | Loading memory, experience, and checkpoint stores from disk on app launch. | < 20 ms |
| **Run State Resume** | `agent.resume(run_id)` state restoration latency. | < 5 ms |
| **Memory Footprint** | RAM usage during active agent orchestration loop. | < 100 MB |
| **Battery Impact** | Power consumption delta during 100 consecutive background runs. | Minimal (< 1% battery / 100 runs) |
| **Offline Execution Latency** | E2E run latency when cellular and Wi-Fi are disabled. | Identical to online local run |

---

## 2. Benchmark Execution Methodology

### Test Environment Requirements
- **Device Class**: Physical iPhone device running iOS 17+ or Xcode iOS Simulator.
- **Network Modes**:
  1. **Fully Offline**: Wi-Fi disabled, Airplane Mode enabled.
  2. **Cellular / Wi-Fi Active**: Live internet connectivity for external capabilities.
- **Iterations**: Minimum 20 iterations per metric to establish statistical average, min, max, and standard deviation.

---

## 3. Reporting Artifact Format

Results must be saved in JSON format matching the schema:

```json
{
  "benchmark_id": "ios_native_runtime_v01",
  "timestamp": "2026-09-04T00:00:00Z",
  "environment": {
    "device_model": "iPhone 15 Pro",
    "ios_version": "17.5",
    "offline_mode": true
  },
  "metrics": {
    "cold_start_ms": 180.2,
    "agent_init_ms": 12.4,
    "memory_rw_avg_ms": 0.04,
    "vault_rw_avg_ms": 0.01,
    "agent_run_avg_ms": 194.5,
    "capability_discovery_ms": 0.05,
    "capability_exec_ms": 8.2,
    "policy_auth_ms": 0.01,
    "persistence_reload_ms": 2.1,
    "resume_latency_ms": 0.17,
    "ram_footprint_mb": 42.5
  }
}
```
