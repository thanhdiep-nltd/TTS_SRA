import json
from src.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Đếm assignment cho TOAN_6
    rows = db.execute(text("""
        SELECT COUNT(*) FROM s360.dim_so_assignment 
        WHERE subject_id = 106
    """)).fetchone()
    print(f'Tổng assignment TOAN_6: {rows[0]}')
    
    # Đếm teaching_schedules cho TOAN_6
    rows = db.execute(text("""
        SELECT COUNT(DISTINCT week_number), COUNT(DISTINCT unit_id)
        FROM public.teaching_schedules
        WHERE subject_id = 106 AND grade_number = 6
    """)).fetchone()
    print(f'Số tuần: {rows[0]}, số unit_id: {rows[1]}')
    
    # Danh sách unit_id có trong teaching_schedules
    rows = db.execute(text("""
        SELECT DISTINCT unit_id FROM public.teaching_schedules
        WHERE subject_id = 106 AND grade_number = 6
        AND unit_id IS NOT NULL
        ORDER BY unit_id
    """)).fetchall()
    ts_units = [r[0] for r in rows]
    print(f'Unit_id trong teaching_schedules ({len(ts_units)}): {ts_units}')
    
    # Check unit_id nào có trong templates
    with open('F:/PROJECT_VSF/TTS_SRA/data/question_templates_toan6.json', encoding='utf-8') as f:
        templates = json.load(f)
    template_units = set(int(k) for k in templates.keys())
    print(f'Unit_id trong templates ({len(template_units)}): {sorted(template_units)}')
    
    missing = set(ts_units) - template_units
    if missing:
        print(f'⚠️ Unit_id có trong teaching_schedules nhưng KHÔNG có template: {sorted(missing)}')
    
    extra = template_units - set(ts_units)
    if extra:
        print(f'⚠️ Unit_id có trong templates nhưng KHÔNG trong teaching_schedules: {sorted(extra)}')
    
    # Phân bố Bloom trong templates
    bloom_counts = {}
    for unit_id, v in templates.items():
        for q in v['questions']:
            b = q.get('bloom_level', 0)
            bloom_counts[b] = bloom_counts.get(b, 0) + 1
    print(f'Phân bố Bloom: {sorted(bloom_counts.items())}')
    
finally:
    db.close()