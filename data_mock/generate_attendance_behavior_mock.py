import random
import sys
from datetime import datetime, timedelta
from sqlalchemy import text
from src.db.session import SessionLocal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def seed_attendance_and_behavior_data():
    print("🚀 Starting Attendance & Behavior Mock Data Generator...")
    session = SessionLocal()

    try:
        # 1. SEED s360.dim_behavior (30 Tiêu chí Hành vi & Rèn luyện)
        print("📌 Seeding s360.dim_behavior...")
        behaviors_data = [
            # Nhóm Nếp sống & Chuyên cần (Đi muộn & Nghỉ học)
            (1, "BEH_LATE_MORNING", "Đi học muộn đầu giờ sáng (sau 7h30)", "NEP_SONG", "Nếp sống & Chuyên cần", -2.0, 1, 3, -5.0),
            (2, "BEH_ABSENT_FULLDAY_NO_PERM", "Nghỉ học cả ngày không xin phép", "NEP_SONG", "Nếp sống & Chuyên cần", -5.0, 1, 2, -8.0),
            (3, "BEH_ABSENT_FULLDAY_WITH_PERM", "Nghỉ học cả ngày có đơn xin phép / ốm", "NEP_SONG", "Nếp sống & Chuyên cần", 0.0, 0, 0, 0.0),
            (4, "BEH_ABSENT_PERIOD_NO_PERM", "Vắng mặt / Bỏ tiết học môn phần không lý do", "NEP_SONG", "Nếp sống & Chuyên cần", -3.0, 1, 2, -5.0),
            (5, "BEH_LATE_PERIOD", "Vào lớp muộn sau chuông báo tiết học", "NEP_SONG", "Nếp sống & Chuyên cần", -1.0, 0, 0, 0.0),
            (6, "BEH_LEAVE_EARLY", "Tự ý về sớm trước giờ tan học", "NEP_SONG", "Nếp sống & Chuyên cần", -4.0, 1, 2, -6.0),

            # Nhóm Trang phục & Đồng phục
            (7, "BEH_UNIFORM_WRONG", "Mặc sai đồng phục quy định của trường", "TRANG_PHUC", "Trang phục & Tác phong", -1.0, 0, 0, 0.0),
            (8, "BEH_NO_STUDENT_CARD", "Không đeo thẻ học sinh", "TRANG_PHUC", "Trang phục & Tác phong", -1.0, 0, 0, 0.0),
            (9, "BEH_HAIRCUT_VIOLATION", "Đầu tóc, trang điểm vi phạm nội quy", "TRANG_PHUC", "Trang phục & Tác phong", -2.0, 0, 0, 0.0),

            # Nhóm Nề nếp Học tập trong Lớp
            (10, "BEH_HOMEWORK_MISSING", "Không làm bài tập về nhà", "HOC_TAP", "Nề nếp Học tập", -2.0, 1, 3, -4.0),
            (11, "BEH_NO_EQUIPMENT", "Thiếu sách vở / dụng cụ học tập", "HOC_TAP", "Nề nếp Học tập", -1.0, 0, 0, 0.0),
            (12, "BEH_CELLPHONE_CLASS", "Sử dụng điện thoại riêng trong giờ học", "HOC_TAP", "Nề nếp Học tập", -3.0, 1, 2, -5.0),
            (13, "BEH_TALKING_IN_CLASS", "Mất trật tự, làm việc riêng trong giờ", "HOC_TAP", "Nề nếp Học tập", -1.0, 0, 0, 0.0),
            (14, "BEH_CHEATING_TEST", "Gian lận trong khi làm bài kiểm tra", "HOC_TAP", "Nề nếp Học tập", -10.0, 0, 0, 0.0),

            # Nhóm Kỷ luật & Văn hóa Giao tiếp
            (15, "BEH_BAD_LANGUAGE", "Nói tục, chửi thề trong khuôn viên trường", "KY_LUAT", "Kỷ luật & Giao tiếp", -3.0, 0, 0, 0.0),
            (16, "BEH_LITTERING", "Xả rác bừa bãi không đúng nơi quy định", "KY_LUAT", "Kỷ luật & Giao tiếp", -2.0, 0, 0, 0.0),
            (17, "BEH_DISRESPECT_TEACHER", "Cãi lời / Vô lễ với thầy cô giáo", "KY_LUAT", "Kỷ luật & Giao tiếp", -10.0, 0, 0, 0.0),
            (18, "BEH_FIGHTING", "Gây nổ đố / Đánh nhau trong trường", "KY_LUAT", "Kỷ luật & Giao tiếp", -15.0, 0, 0, 0.0),

            # Nhóm Khen thưởng & Tích cực (Cộng điểm)
            (19, "BEH_GOOD_DEED", "Nhặt được của rơi trả lại người mất", "KHEN_THUONG", "Khen thưởng & Việc tốt", 5.0, 0, 0, 0.0),
            (20, "BEH_HELP_PEER", "Tích cực phụ đạo / Giúp đỡ bạn học tiến bộ", "KHEN_THUONG", "Khen thưởng & Việc tốt", 3.0, 0, 0, 0.0),
            (21, "BEH_SCHOOL_EVENT_VOLUNTEER", "Hỗ trợ tích cực sự kiện truyền thông của trường", "KHEN_THUONG", "Khen thưởng & Việc tốt", 4.0, 0, 0, 0.0),
            (22, "BEH_CLEAN_CLASSROOM", "Chủ động vệ sinh giữ gìn lớp học sạch đẹp", "KHEN_THUONG", "Khen thưởng & Việc tốt", 2.0, 0, 0, 0.0),
        ]

        for b in behaviors_data:
            session.execute(
                text("""
                    INSERT INTO s360.dim_behavior 
                    (id, code, name, group_code, group_name, point, is_duplicate_behavior, count_duplicate_behavior, point_duplicate_behavior)
                    VALUES (:id, :code, :name, :gcode, :gname, :point, :is_dup, :cnt_dup, :pt_dup)
                    ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name, point = EXCLUDED.point, point_duplicate_behavior = EXCLUDED.point_duplicate_behavior;
                """),
                {
                    "id": b[0], "code": b[1], "name": b[2], "gcode": b[3], "gname": b[4],
                    "point": b[5], "is_dup": b[6], "cnt_dup": b[7], "pt_dup": b[8]
                }
            )
        session.commit()
        print("   ✅ Installed 22 Behavior Categories into s360.dim_behavior.")

        # 2. SEED s360.dim_course (Danh mục lớp học phần môn tự chọn)
        print("📌 Seeding s360.dim_course...")
        courses_data = [
            (101, 1, 2025, 7, 2, 14, "CRS_MATH_ADV_7A1", "Lớp Học Phần Toán Nâng Cao 7A1", "ELECTIVE", 35),
            (102, 1, 2025, 7, 3, 14, "CRS_ENG_CAMB_7A1", "Lớp Tiếng Anh Cambridge 7A1", "ELECTIVE", 35),
            (103, 1, 2025, 7, 4, 14, "CRS_STEM_ROBOTICS_7A1", "Lớp STEM & Robotics Khối 7", "ELECTIVE", 35),
            (104, 1, 2025, 7, 5, 15, "CRS_LIT_ADV_7A2", "Lớp Chuyên Ngữ Văn Khối 7", "ELECTIVE", 35),
        ]

        for c in courses_data:
            session.execute(
                text("""
                    INSERT INTO s360.dim_course
                    (id, so_school_id, school_year_id, grade_id, subject_id, homeroom_class_id, code, name, type, max_student)
                    VALUES (:id, :sid, :syid, :gid, :subid, :cid, :code, :name, :type, :max_s)
                    ON CONFLICT (id) DO NOTHING;
                """),
                {
                    "id": c[0], "sid": c[1], "syid": c[2], "gid": c[3], "subid": c[4],
                    "cid": c[5], "code": c[6], "name": c[7], "type": c[8], "max_s": c[9]
                }
            )
        session.commit()
        print("   ✅ Installed sample courses into s360.dim_course.")

        # 3. FETCH STUDENTS FROM s360.dim_homeroom_class_student
        students = session.execute(
            text("""
                SELECT student_code, student_name, homeroom_class_id, grade_id, so_school_id, school_year_id
                FROM s360.dim_homeroom_class_student
                WHERE so_school_id = 1
            """)
        ).fetchall()

        if not students:
            print("⚠️ No active students found in s360.dim_homeroom_class_student! Skipping fact seeding.")
            return

        print(f"📌 Found {len(students)} students. Seeding Fact Logs (70/20/10 Distribution)...")

        # 4. GENERATE FACT LOGS (Pareto Distribution)
        start_date = datetime(2025, 9, 5) # Đầu năm học 2025-2026
        now_date = datetime(2026, 1, 15)

        total_days = (now_date - start_date).days
        school_dates = [start_date + timedelta(days=i) for i in range(total_days) if (start_date + timedelta(days=i)).weekday() < 5]

        # Categorize students into 70% Good, 20% Occasional, 10% At-Risk
        random.seed(42) # Deterministic for consistent testing
        shuffled_students = list(students)
        random.shuffle(shuffled_students)

        num_students = len(shuffled_students)
        at_risk_cutoff = int(num_students * 0.10)
        occasional_cutoff = int(num_students * 0.30)

        at_risk_students = shuffled_students[:at_risk_cutoff]
        occasional_students = shuffled_students[at_risk_cutoff:occasional_cutoff]
        good_students = shuffled_students[occasional_cutoff:]

        print(f"   👥 Student Distribution: {len(good_students)} Good (70%), {len(occasional_students)} Occasional (20%), {len(at_risk_students)} At-Risk (10%).")

        behavior_logs_count = 0
        absent_logs_count = 0
        late_logs_count = 0

        # Helper to generate dates
        for st in shuffled_students:
            st_code, st_name, class_id, grade_id, school_id, sy_id = st

            if st in at_risk_students:
                # 5-10 behavior violations, 3-6 late attendances, 2 unexcused absences
                num_violations = random.randint(5, 10)
                num_lates = random.randint(3, 6)
                num_absents = random.randint(2, 4)
            elif st in occasional_students:
                num_violations = random.randint(1, 3)
                num_lates = random.randint(1, 2)
                num_absents = random.randint(0, 2)
            else: # Good students
                num_violations = 1 if random.random() < 0.2 else 0
                num_lates = 1 if random.random() < 0.15 else 0
                num_absents = 1 if random.random() < 0.1 else 0

            # A. Generate Behavior Logs
            for _ in range(num_violations):
                log_date = random.choice(school_dates)
                if st in at_risk_students and random.random() < 0.7:
                    # Pick late or cellphone or unexcused absent
                    b_id, b_code, b_name, b_point = random.choice([
                        (1, "BEH_LATE_MORNING", "Đi học muộn đầu giờ sáng (sau 7h30)", -2.0),
                        (2, "BEH_ABSENT_FULLDAY_NO_PERM", "Nghỉ học cả ngày không xin phép", -5.0),
                        (12, "BEH_CELLPHONE_CLASS", "Sử dụng điện thoại riêng trong giờ học", -3.0),
                        (10, "BEH_HOMEWORK_MISSING", "Không làm bài tập về nhà", -2.0)
                    ])
                else:
                    b_id, b_code, b_name, b_point = random.choice([
                        (7, "BEH_UNIFORM_WRONG", "Mặc sai đồng phục quy định của trường", -1.0),
                        (8, "BEH_NO_STUDENT_CARD", "Không đeo thẻ học sinh", -1.0),
                        (19, "BEH_GOOD_DEED", "Nhặt được của rơi trả lại người mất", 5.0),
                        (20, "BEH_HELP_PEER", "Tích cực phụ đạo / Giúp đỡ bạn học tiến bộ", 3.0)
                    ])

                session.execute(
                    text("""
                        INSERT INTO s360.fact_behavior_logs
                        (so_school_id, school_year_id, student_code, behavior_id, behavior_code, behavior_fullname, behavior_point, behavior_comment, comment_date)
                        VALUES (:sid, :syid, :scode, :bid, :bcode, :bname, :bpt, :bcmt, :cdate);
                    """),
                    {
                        "sid": school_id, "syid": sy_id, "scode": st_code, "bid": b_id,
                        "bcode": b_code, "bname": b_name, "bpt": b_point,
                        "bcmt": f"Ghi nhận nếp sống ngày {log_date.strftime('%d/%m/%Y')}", "cdate": log_date.date()
                    }
                )
                behavior_logs_count += 1

            # B. Generate Late Attendances
            for _ in range(num_lates):
                late_date = random.choice(school_dates)
                minutes_late = random.randint(10, 35)
                session.execute(
                    text("""
                        INSERT INTO s360.fact_so_homeroom_class_late_attendances
                        (so_school_id, school_year_id, grade_id, homeroom_class_id, attendance_date, student_code, user_fullname, attendance_time, is_late, status_name, time_late)
                        VALUES (:sid, :syid, :gid, :cid, :adate, :scode, :sname, :atime, 1, 'DI_MUON', :tlate);
                    """),
                    {
                        "sid": school_id, "syid": sy_id, "gid": grade_id, "cid": class_id,
                        "adate": late_date.date(), "scode": st_code, "sname": st_name or "Học sinh",
                        "atime": datetime.combine(late_date.date(), datetime.min.time()) + timedelta(hours=7, minutes=30+minutes_late),
                        "tlate": minutes_late
                    }
                )
                late_logs_count += 1

            # C. Generate Absent Logs
            for _ in range(num_absents):
                abs_date = random.choice(school_dates)
                is_excused = random.random() < 0.6 if st not in at_risk_students else random.random() < 0.2
                reason_cat = "CO_PHEP" if is_excused else "KHONG_PHEP"
                reason_txt = "Nghỉ ốm có đơn xin phép của phụ huynh" if is_excused else "Nghỉ học không lý do"

                session.execute(
                    text("""
                        INSERT INTO s360.fact_absent_logs
                        (so_school_id, school_year_id, homeroom_class_id, student_code, reason, reason_category, from_date, to_date, is_approved, absent_date)
                        VALUES (:sid, :syid, :cid, :scode, :reason, :rcat, :adate, :adate, :app, :adate);
                    """),
                    {
                        "sid": school_id, "syid": sy_id, "cid": class_id, "scode": st_code,
                        "reason": reason_txt, "rcat": reason_cat, "adate": abs_date.date(),
                        "app": 1 if is_excused else 0
                    }
                )
                absent_logs_count += 1

        session.commit()
        print(f"   ✅ Successfully seeded {behavior_logs_count} behavior logs, {late_logs_count} tardiness records, and {absent_logs_count} absence logs!")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding attendance & behavior data: {e}")
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    seed_attendance_and_behavior_data()
