# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: high_latency_p95
- Severity: warning
- SLI/SLO liên quan: `latency_p95_ms` (objective ≤ 3000ms, target 99.5%)
- Điều kiện và thời gian duy trì: P95 latency > 3000ms, duy trì liên tục 5 phút
- Ảnh hưởng tới người dùng: câu trả lời chậm, có thể timeout ở client
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency trên dashboard, xác nhận khoảng thời gian P95 vượt ngưỡng
  2. Mở một trace chậm trong khoảng đó trên Langfuse, so sánh thời gian các span (retrieval, generation)
  3. Tìm log có cùng `correlation_id` với trace đó để xem chi tiết bước nào chiếm nhiều thời gian nhất
- Mitigation tạm thời: tắt incident practice nếu đang bật (`python scripts/inject_incident.py --scenario rag_slow --disable`), hoặc giảm concurrency của load test/traffic thực tế
- Owner: Dashboard, SLO & Alert

## Alert 2

- Tên: high_error_rate
- Severity: critical
- SLI/SLO liên quan: `error_rate_pct` (objective ≤ 2%, target 99.0%)
- Điều kiện và thời gian duy trì: tỷ lệ `request_failed`/`request_received` > 2%, duy trì liên tục 5 phút
- Ảnh hưởng tới người dùng: request bị lỗi 500, không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors, xem breakdown theo `error_type` để biết lỗi nào chiếm đa số
  2. Mở trace ứng với request lỗi, xác định span nào raise exception
  3. Tìm log `request_failed` cùng `correlation_id`, đọc `payload.detail` để biết nguyên nhân cụ thể
- Mitigation tạm thời: tắt incident practice liên quan (`python scripts/inject_incident.py --scenario tool_fail --disable`); nếu là lỗi thực tế, tạm thời giảm tải hoặc rollback thay đổi gần nhất
- Owner: Dashboard, SLO & Alert

## Alert 3

- Tên: cost_budget_exceeded
- Severity: warning
- SLI/SLO liên quan: `daily_cost_usd` (objective ≤ 2.5 USD, target 100%)
- Điều kiện và thời gian duy trì: tổng `cost_usd` trong cửa sổ 60 phút > 2.5 USD, duy trì 15 phút
- Ảnh hưởng tới người dùng: không ảnh hưởng trực tiếp trải nghiệm, nhưng rủi ro vượt ngân sách vận hành
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Cost, xem xu hướng cost theo phút và tổng cửa sổ hiện tại
  2. Mở panel Tokens để xem tokens_in/tokens_out có tăng bất thường không
  3. Mở trace có cost cao nhất trên Langfuse, kiểm tra input/output token count và model đang dùng
- Mitigation tạm thời: tắt incident practice (`python scripts/inject_incident.py --scenario cost_spike --disable`); nếu thực tế, giới hạn rate hoặc chuyển tạm sang model rẻ hơn
- Owner: Dashboard, SLO & Alert
