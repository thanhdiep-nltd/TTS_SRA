# Antigravity Rules - Core Architecture & Execution Principles

## 1. QUY TRÌNH & ĐIỀU PHỐI (Workflow & Collaboration)
- LUÔN LUÔN lên kế hoạch chi tiết (Planning Mode) và trình bày thiết kế kiến trúc trước khi triển khai tính năng mới hoặc refactor lớn.
- Chỉ tiến hành viết code khi người dùng đã xem duyệt và xác nhận bản kế hoạch (implementation_plan.md).
- Luôn trao đổi, giải thích và viết tài liệu bằng tiếng Việt.

## 2. NGUYÊN TẮC THIẾT KẾ & TƯ DUY NỀN TẢNG (Architecture & Problem Solving)
- Giải quyết bài toán ở TẦNG GỐC RỄ: Phân tích kỹ nguyên nhân cốt lõi (Root Cause) của vấn đề. Tránh dùng các giải pháp vá lỗi tạm thời, chắp vá cục bộ (Quick Fix) gây nợ kỹ thuật (Technical Debt).
- Tận dụng Mẫu thiết kế chuẩn (Industry Best Practices): Áp dụng các Pattern đã được kiểm chứng từ các Framework lớn (LangGraph Enterprise, OpenAI Assistants, LlamaIndex Workflows...).
- Ưu tiên tính bền vững: Thiết kế hệ thống theo tiêu chuẩn Dễ mở rộng (Maintainable), Linh hoạt trước sự thay đổi của yêu cầu thực tế và Tận dụng tối đa Native Capabilities của hệ sinh thái.
- Khi 1 testcase fail, cần hiểu rỏ root cause của nó. KHÔNG ĐƯỢC sửa testcase để pass/cố sửa code để pass. Hãy thông báo cho tôi testcase nào đang sai. Để tôi có thể xem lại testcase đó có cần fix hay không.

## 3. TIÊU CHUẨN ĐÁNH GIÁ KẾ HOẠCH (Planning Checklist)
Một bản Kế hoạch (Plan) đạt chuẩn cần đáp ứng 3 câu hỏi:
1. Giải pháp có hoạt động ổn định trước sự đa dạng văn phong và hành vi thực tế của người dùng không?
2. Kiến trúc có dễ bảo trì, dễ kiểm thử và mở rộng khi hệ thống phát triển lớn hơn không?
3. Giải pháp có tuân thủ đúng các chuẩn Native và Mẫu thiết kế tốt nhất của Framework/Provider đang dùng không?