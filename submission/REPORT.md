# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: DiemQuynh10 (làm solo)
- Repository URL: https://github.com/DiemQuynh10/Day13-K3-Observability
- Commit SHA cuối: `4692df0` (4 commit tách vai trò: `b0ebb25` Logging & PII, `d01225e` Tracing & Prompt Version, `dade0b1` Dashboard/SLO/Alert, `4692df0` Report)
- Thành viên và vai trò: Diễm Quỳnh — kiêm toàn bộ 4 vai trò (Logging & PII; Tracing & Prompt Version; Dashboard, SLO & Alert; Incident, Report & Demo), theo đúng quy định "một người có thể giữ nhiều vai trò khi làm solo/nhóm ít người" (README.md).

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (xem `submission/evidence/validate_logs_result.png`)
- Tổng số traces: **≥ 16** trên Langfuse (11 traces baseline + 5 traces challenge `refund`)
- Số PII leak còn lại: **0** (email, số điện thoại, số thẻ tín dụng đều bị redact — `submission/evidence/log_correlation_pii.png`)
- Link/đường dẫn dashboard: `python -m streamlit run scripts/dashboard.py` → `http://localhost:8501` (đọc trực tiếp từ `data/logs.jsonl`, evidence `submission/evidence/dashboard_*.png`)

## 3. Logging và tracing

- Evidence correlation ID: mọi request có 1 `correlation_id` duy nhất dạng `req-<8-hex>`, xuất hiện đồng nhất ở cả `request_received` và `response_sent` (xem `submission/evidence/log_correlation_pii.png`, VD `correlation_id: req-17d7163d`); cũng được trả về qua response header `x-request-id`.
- Evidence PII redaction: test với email/SĐT/thẻ tín dụng mẫu → tất cả bị thay bằng `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]` trước khi ghi xuống `data/logs.jsonl` (processor `scrub_event` chạy trước `JsonlFileProcessor` trong `app/logging_config.py`).
- Evidence trace waterfall: `submission/evidence/trace_waterfall.png` — trace `e873f9bebb04aad007836475ac7e2f3f`, cấu trúc `run` (span cha) → `run` (generation con), cùng 1.31s, $0.001902.
- Giải thích một span đáng chú ý: span `GENERATION` bên trong mỗi trace mang toàn bộ metadata prompt (`prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`) và usage/cost, cho phép truy vết chính xác request đã dùng prompt version nào mà không cần đọc log.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: version **1**, label `baseline` (ban đầu cũng giữ `production`)
- Version/label candidate: version **2**, label `candidate`
- Trace ID của mỗi version:
  - baseline (v1): `1e7b8dfa37f491d2a3dfa3607b1a992b`
  - candidate (v2): `292044462ba7ea74939d7f07472d3aaf`
- Bằng chứng đổi label hoặc rollback:
  1. Chuyển `production` từ v1 → v2, verify qua trace `e873f9bebb04aad007836475ac7e2f3f` (`prompt_label=production`, `prompt_version=2`).
  2. Rollback `production` v2 → v1. Trạng thái cuối: v1 = `[baseline, production]`, v2 = `[candidate, latest]` — evidence `submission/evidence/prompt_rollback.png`, `prompt_v1_linked_generations.png`, `prompt_v2_linked_generations.png`.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **HỢP LỆ: 6/6 panel** (`submission/evidence/validate_dashboard_result.png`)
- Evidence dashboard: `submission/evidence/dashboard_1_latency.png` … `dashboard_5_quality.png` — dashboard Streamlit tự viết (`scripts/dashboard.py`), đọc trực tiếp `data/logs.jsonl`, time range 60 phút, refresh 30s, mỗi panel có tên/đơn vị/threshold theo đúng `config/dashboard.yaml`.
- SLO đã chọn và lý do (`config/slo.yaml`):
  - `latency_p95_ms <= 3000` (target 99.5%) — ngưỡng chấp nhận được cho trải nghiệm chat.
  - `error_rate_pct <= 2` (target 99.0%) — đảm bảo tỷ lệ lỗi thấp.
  - `daily_cost_usd <= 2.5` (target 100%) — giới hạn ngân sách vận hành.
  - `quality_score_avg >= 0.75` (target 95%) — đảm bảo chất lượng câu trả lời tối thiểu.
- Alert rules và runbook (`config/alert_rules.yaml`, `docs/alerts.md`):
  - `high_latency_p95` (warning) — P95 > 3000ms trong 5 phút.
  - `high_error_rate` (critical) — error rate > 2% trong 5 phút.
  - `cost_budget_exceeded` (warning) — cost > $2.5 trong 15 phút.
  - Mỗi alert có runbook chi tiết: SLI liên quan, ảnh hưởng người dùng, 3 bước kiểm tra đầu tiên, mitigation tạm thời, owner.

## 6. Điều tra challenge

- Challenge ID: `day13-k3-observability-v1` (cohort K3), incident `rag_slow`, feature bị ảnh hưởng: `refund`, ngưỡng latency: 2000ms.
- Triệu chứng từ metrics: chạy `python scripts/load_test.py --challenge --concurrency 5` → latency đo phía client **tăng lũy tiến bất thường**: 5321ms → 13285ms → 13286ms → 13285ms → 13285ms (baseline bình thường chỉ ~150-1300ms).
- Trace ID liên quan (Langfuse, feature `refund`):
  - `7de4b28bb89e6af1e1e5632f7eb7096a` (session `k3-challenge-s01`) — latency nội bộ 2.652s
  - `68d0c42d0fd2e264aead45c504ea5163` (session `k3-challenge-s04`) — 2.652s
  - `9efc6dac7e022d46b8d8dd0cc76c3c66` (session `k3-challenge-s03`) — 2.653s
  - `60eac36c844b739e3bb415d252b8750b` (session `k3-challenge-s02`) — 2.653s
  - `eb724ddae67c31319c55e6f0af6382ff` (session `k3-challenge-s05`) — 2.655s
  - Quan trọng: `end_time` của trace trước gần như trùng khớp `start_time` của trace sau (VD 03:57:11.894 → 03:57:11.898) → 5 request chạy **tuần tự**, không song song dù `--concurrency 5`.
- Log line/correlation ID liên quan (`data/logs.jsonl`): `req-abd2c65d`, `req-b3fb066b`, `req-551657bd`, `req-bb12d33f`, `req-3db74d28` — field `latency_ms` server tự đo **ổn định ở 2651ms** cho cả 5 request, trong khi latency client đo được (từ `load_test.py`) tăng dần lên tới 13286ms. Sự chênh lệch này là bằng chứng trực tiếp cho việc request bị xếp hàng chờ (queueing) chứ không phải RAG chậm đơn thuần.
- Root cause: `app/mock_rag.py:16` gọi `time.sleep(2.5)` — một blocking call đồng bộ — bên trong `retrieve()`, được gọi từ `LabAgent.run()` (một hàm sync, không async) trực tiếp trong async endpoint `/chat` (`app/main.py`) mà không được offload sang threadpool. Khi `rag_slow` bật, `time.sleep()` chặn đứng toàn bộ event loop của uvicorn/FastAPI, khiến các request đến sau phải chờ request trước xử lý xong mới được nhận — hiệu ứng khuếch đại: latency thực tế của request cuối ≈ N × 2.5s thay vì chỉ +2.5s so với baseline.
- Fix action: đổi `retrieve()`/`agent.run()` sang non-blocking — dùng `await asyncio.sleep()` thay `time.sleep()`, hoặc bọc lời gọi `agent.run()` bằng `starlette.concurrency.run_in_threadpool` để không chặn event loop chính; đã xác nhận sau khi tắt incident, latency về lại 150ms (`req-0ff7deda`).
- Preventive measure: thêm alert dựa trên **chênh lệch giữa latency đo server-side (`response_sent.latency_ms`) và latency đo client/gateway-side** — khi 2 giá trị lệch nhau lớn dần theo thời gian, đó là dấu hiệu event loop bị block/serialize, cần phát hiện trước khi ảnh hưởng người dùng thật trên production; đồng thời review code để đảm bảo mọi blocking I/O (sleep, gọi mạng đồng bộ) đều được chạy trong threadpool hoặc chuyển sang async.

## 7. Đóng góp cá nhân

Làm solo nên một mình đảm nhiệm toàn bộ 4 mảng việc:

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Diễm Quỳnh | Logging & PII: correlation ID middleware, enrich context, PII scrubbing pattern/pipeline | `b0ebb25` | Structlog contextvars phải được bind **trước** log đầu tiên trong request mới có tác dụng; PII processor phải đứng **trước** JSONRenderer/file writer trong pipeline, sai thứ tự là log vẫn lộ dữ liệu gốc dù có viết regex đúng. |
| Diễm Quỳnh | Tracing & Prompt Version: tạo prompt v1/v2 qua Langfuse SDK, đổi label, rollback, verify qua trace metadata | `d01225e` | Langfuse đảm bảo mỗi label chỉ gắn đúng 1 version tại một thời điểm (gắn `production` cho v2 sẽ tự động gỡ khỏi v1) — rollback vì vậy chỉ cần gọi lại `update_prompt` với version cũ, không cần thao tác gì thêm trên các version khác. |
| Diễm Quỳnh | Dashboard, SLO & Alert: viết dashboard Streamlit đọc `data/logs.jsonl` theo đúng contract, hoàn thiện `alert_rules.yaml` và runbook | `dade0b1` | Sự khác biệt giữa "validator pass" và "dashboard đúng" — `validate_dashboard.py` chỉ kiểm tra cấu trúc YAML, không kiểm tra logic tính toán thật; phải tự đối chiếu từng panel với dữ liệu log thực tế mới chắc chắn đúng. |
| Diễm Quỳnh | Incident, Report & Demo: chạy challenge chính thức, điều tra root cause qua 3 lớp Metrics → Traces → Logs, viết báo cáo | (commit report — xem SHA cuối ở mục 1) | Latency đo phía server (`response_sent.latency_ms`) và latency đo phía client có thể lệch nhau rất lớn khi có blocking I/O trong code async — chênh lệch này tự nó là một tín hiệu chẩn đoán, không cần đợi biết root cause chi tiết mới nghi ngờ được vấn đề serialization. |
