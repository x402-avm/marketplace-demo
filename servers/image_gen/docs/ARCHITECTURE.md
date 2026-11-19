# Gemini Nano Banana Architecture

This project implements a multi-agent image generation & editing system running exclusively on the **AMD Ryzen AI 9 HX 370 CPU (Zen 5, 24 threads)** with complete isolation of the NVIDIA GeForce RTX 4070 discrete GPU.

## Design Principles
- **No ComfyUI**: 100% self-contained native Python architecture.
- **Strict dGPU Isolation**: `CUDA_VISIBLE_DEVICES=""` enforced at process start; discrete GPU is locked out.
- **Port Compliance**: All services strictly bind to ports in the range `10000-10100`.
- **Multi-Agent Orchestration**: Prompt Engineer, CPU Inference Engine, QA Critic, and Hardware Guardian coordinate automatically.

## Topology

```mermaid
graph TD
    Client[Web Browser / User] -->|HTTP / Web UI| R[Central Runtime Server :10000]
    MCP1[MCP Client] -->|SSE :10002| M1[FastMCP Server 1]
    MCP2[MCP Client] -->|SSE :10003| M2[FastMCP Server 2]
    M1 -->|HTTP POST| R
    M2 -->|HTTP POST| R
    
    subgraph Multi-Agent Engine
        R --> A1[Agent 1: AI Prompt Engineer]
        A1 --> A2[Agent 2: CPU Inference & CV Processor]
        A2 --> A3[Agent 3: QA Critic Agent]
        A3 --> Out[(Outputs & Audits)]
        H[Agent 4: Hardware Guardian] -.->|Enforce CPU| A2
    end
```
