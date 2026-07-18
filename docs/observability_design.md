# Tài Liệu Thiết Kế: Hệ Thống Observability & Smart Alerting (AgentOps)

## 1. Tổng Quan (Overview)
Hệ thống **C2-App-051** là một **Compound AI System** phức tạp bao gồm FastAPI Backend, LangGraph Agent, RAG Pipeline và Qdrant Vector DB. Việc giám sát hệ thống này đòi hỏi một cách tiếp cận vượt ra khỏi monitoring truyền thống (chỉ kiểm tra HTTP 200 hay CPU/RAM) để chuyển sang **AgentOps Observability**.

Tài liệu này thiết kế một kiến trúc giám sát toàn diện với **4 trụ cột (Metrics, Logs, Traces, Eval)** và một hệ thống **Cảnh báo Thông minh (Smart Alerting) qua Telegram/SMS**, nhằm phát hiện sớm các sự cố (hallucination, infinite loop, cạn ngân sách) trước khi người dùng kịp phàn nàn.

## 2. Kiến Trúc Tổng Thể (Architecture)

```mermaid
graph TD
    subgraph "Application Layer (C2-App-051)"
        API[FastAPI Backend]
        Agent[LangGraph Agent]
        Tools[Agent Tools]
        PII[Presidio PII Redactor]
        
        API & Agent & Tools --> PII
        PII -->|JSON + TraceID| Log[structlog]
        PII -->|OTel Spans| Trace[OpenTelemetry SDK]
        Agent -->|Token/Cost/Latency| Metric[Prometheus Client]
    end

    subgraph "Observability Backend"
        OTelCol[OTel Collector]
        Prom[Prometheus - Metrics]
        Loki[Loki - Logs]
        Langfuse[Langfuse - Traces/Eval]
        
        Trace & Log & Metric --> OTelCol
        OTelCol --> Prom
        OTelCol --> Loki
        OTelCol --> Langfuse
    end

    subgraph "Smart Alerting System"
        AlertMgr[Alertmanager]
        WebHook[Telegram/SMS Webhook Service]
        
        Prom -->|Burn-rate/Symptom Alerts| AlertMgr
        AlertMgr --> WebHook
    end

    subgraph "Stakeholders"
        Grafana[Grafana Dashboards]
        Telegram[Telegram / SMS (Owner/Leader)]
        
        Prom & Loki --> Grafana
        WebHook --> Telegram
    end
```

## 3. Các Trụ Cột Giám Sát Chi Tiết

### 3.1. Structured Logging & PII Redaction
- **Công cụ:** `structlog` (Python).
- **Tính năng:** Chuyển đổi toàn bộ log thành định dạng JSON. Đính kèm `correlation_id` vào mọi request thông qua Middleware để xâu chuỗi log xuyên suốt các service.
- **Bảo mật PII (Luật PDPL 91/2025):** Tích hợp **Microsoft Presidio** làm middleware ngay trong code để tự động che khuất (mask) các thông tin nhạy cảm (SĐT, Email, CCCD) trước khi log được đẩy ra ngoài. VD: `0901234567` -> `[PHONE_REDACTED]`.

### 3.2. Metrics & FinOps (Quản Trị Chi Phí)
- **Công cụ:** `prometheus_client`.
- **First-Class Metrics:**
  - `agent_latency_seconds_bucket`: Tính P50/P95/P99 latency và TTFT (Time To First Token).
  - `agent_tokens_total` (in/out): Output token luôn đắt gấp 5-6 lần input token.
  - `cost_per_task`: Tính chi phí theo luồng logic của task thay vì từng LLM call lẻ tẻ.

### 3.3. Distributed Tracing & Span Tree
- **Công cụ:** OpenTelemetry (`gen_ai.*` semantic conventions) và **Langfuse**.
- **Tính năng:** Trực quan hóa toàn bộ vòng lặp của LangGraph thành một Cây Span (Trace Waterfall). Nếu một request mất 10s, kỹ sư có thể xem ngay bước RAG (Vector DB) mất bao lâu, bước LLM Synthesize mất bao lâu mà không cần đoán mò. Giúp Debug nhanh chóng các vòng lặp ẩn.

### 3.4. Pillar 4: Eval-as-a-Metric
- Lấy ngẫu nhiên 1-5% Production Traffic để chấm điểm thông qua LLM-as-a-Judge (như framework **Ragas**).
- Các điểm số `Faithfulness` (Độ bám sát) và `Answer Relevancy` được đẩy vào Prometheus dạng Gauge. Cho phép theo dõi chất lượng câu trả lời realtime.

---

## 4. Smart Alerting & Predictive Notifications (Thiết Kế Cốt Lõi)

Hệ thống cảnh báo được thiết kế theo phương pháp **Multi-Window Multi-Burn-Rate** của Google SRE để loại bỏ "Alert Fatigue" (báo động rác) và tích hợp luồng cảnh báo khẩn cấp (Predictive Alert).

### 4.1. Luồng Cảnh Báo Khẩn (Predictive Alerting qua Telegram/SMS)
Thay vì chờ server sập, hệ thống theo dõi **tốc độ đốt ngân sách (Burn-rate)** và **tốc độ tăng lỗi (Error trend)** để báo cáo trước cho Leader/Owner.

- **Thành phần:** Prometheus -> Alertmanager -> Node.js/Python Webhook -> Telegram Bot API / SMS Gateway (Twilio/Nexmo).
- **Kịch bản Cảnh Báo Sớm (Predictive Alerts):**
  - **Sắp Cạn Ngân Sách (Budget Warning):** "Chi phí LLM trong 6 giờ qua đã đạt 80% giới hạn trong ngày. Dự kiến sẽ vượt ngân sách vào lúc 15:00."
  - **Dấu hiệu Suy Thoái Chất Lượng (Quality Degradation):** "Điểm Ragas Faithfulness giảm trung bình 15% trong 30 phút qua. Nguy cơ Agent đang ảo giác (hallucination) hàng loạt."
  - **Agent Runaway (Kẹt vòng lặp vô tận):** "Có 5% các session LangGraph đang vượt quá 10 bước (steps) và không có kết quả." -> Kích hoạt Circuit Breaker tự ngắt và bắn SMS cho Engineer trực ca.

### 4.2. Cấu Trúc Rule Cảnh Báo (Ví Dụ)

```yaml
groups:
- name: AgentOpsAlerts
  rules:
  # Cảnh báo 1: Chi phí bất thường (Predictive)
  - alert: HighCostBurnRate
    expr: rate(cost_per_task_total[1h]) > (daily_budget_limit / 24) * 1.5
    for: 15m
    labels:
      severity: warning
      channel: telegram
    annotations:
      summary: "⚠️ [CẢNH BÁO SỚM] Tốc độ tiêu thụ ngân sách LLM cao bất thường."
      description: "Tốc độ chi tiêu hiện tại đang cao gấp 1.5 lần dự kiến. Sẽ vượt ngân sách ngày nếu tiếp tục."

  # Cảnh báo 2: Chất lượng Agent giảm (Symptom-based)
  - alert: AgentHallucinationSpike
    expr: avg_over_time(eval_score_gauge{metric="faithfulness"}[15m]) < 0.80
    for: 5m
    labels:
      severity: critical
      channel: sms_and_telegram
    annotations:
      summary: "🚨 [NGUY HIỂM] Độ chính xác của Agent tụt xuống dưới 80%."
      description: "Có khả năng Agent đang sinh ra thông tin bịa đặt. Link Trace: {langfuse_url}"
```

## 5. Các Bước Triển Khai (Milestones)

- **Giai đoạn 1:** Tích hợp `structlog` và `presidio` vào FastAPI/LangGraph.
- **Giai đoạn 2:** Expose `/metrics` qua `prometheus_client` cho Token, Cost và Latency P95.
- **Giai đoạn 3:** Dựng hệ thống `docker-compose` gồm Prometheus, Grafana, Alertmanager và Webhook Bot cho Telegram.
- **Giai đoạn 4:** Triển khai OTel/Langfuse để thu thập Trace Tree và bắt đầu tích hợp Eval-as-a-Metric.
