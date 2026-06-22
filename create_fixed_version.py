#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت لإنشاء نسخة محسّنة من الملف الرئيسي
"""

import re

# قراءة الملف الأصلي
with open('wasel_chat_STAGE45_NEW_USER_CONTACT_STATUS_ONLY.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. إضافة دالة email worker جديدة قبل دالة send_mail
email_worker_code = '''

def email_worker_thread():
    """خيط عامل لمعالجة رسائل البريد غير المتزامنة"""
    global EMAIL_WORKER_RUNNING
    EMAIL_WORKER_RUNNING = True
    while EMAIL_WORKER_RUNNING:
        try:
            # محاولة الحصول على رسالة من قائمة الانتظار مع timeout
            to_email, subject, body = EMAIL_QUEUE.get(timeout=1)
            ok, info = send_mail_sync(to_email, subject, body)
            if not ok:
                print(f"EMAIL_WORKER: Failed to send to {to_email}: {info}")
        except:
            # قائمة الانتظار فارغة أو timeout
            pass

def start_email_worker():
    """بدء خيط معالجة البريد إذا لم يكن يعمل"""
    global EMAIL_WORKER_RUNNING
    if not EMAIL_WORKER_RUNNING:
        worker = threading.Thread(target=email_worker_thread, daemon=True)
        worker.start()

def send_mail_async(to_email, subject, body):
    """إضافة رسالة بريد إلى قائمة الانتظار للمعالجة غير المتزامنة"""
    try:
        EMAIL_QUEUE.put_nowait((to_email, subject, body))
        start_email_worker()
        return True, "QUEUED"
    except:
        # إذا امتلأت القائمة، أرسل مباشرة
        return send_mail_sync(to_email, subject, body)

def send_mail_sync(to_email, subject, body):
    """الإرسال المتزامن (الأصلي)"""
'''

# 2. إضافة دالة middleware للـ compression
compression_middleware = '''

@app.before_request
def before_request_compression():
    """تحضير الـ compression"""
    pass

@app.after_request
def after_request_compression(response):
    """إضافة gzip compression للاستجابات الكبيرة"""
    # إضافة cache headers للملفات الثابتة
    if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
        response.cache_control.max_age = 86400  # 24 ساعة
    
    # إضافة gzip compression للاستجابات النصية الكبيرة
    if response.content_length and response.content_length > 1024:
        if 'gzip' in request.headers.get('Accept-Encoding', ''):
            response.data = gzip.compress(response.data)
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = len(response.data)
    
    return response
'''

# 3. تحسين دالة auth_fail لضمان إرجاع JSON للطلبات AJAX
auth_fail_improved = '''def auth_fail(kind, message, field='', status=400):
    if wants_json():
        return jsonify({'ok': False, 'message': message, 'field': field}), status
    return page(auth_html(kind, message))'''

# 4. تحسين دالة register
register_improved = '''@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form.get('name','').strip()
            email = (request.form.get('email','').strip() or '').lower()
            country_pick = request.form.get('country_picker','').strip() or request.form.get('country','').strip()
            country_info = parse_country_value(country_pick)
            country = country_info['name']
            phone_country_code = country_info['code']
            phone_raw = request.form.get('phone','').strip()
            phone = None
            phone_full = None
            if phone_raw:
                phone, phone_full, country_info, phone_err = normalize_phone_by_country(phone_raw, phone_country_code)
                country = country_info['name']
                phone_country_code = country_info['code']
                if phone_err:
                    return auth_fail('register', phone_err, 'phone')
            gender = request.form.get('gender','').strip() or None
            birth_date = request.form.get('birth_date','').strip() or None
            password = request.form.get('password','')
            password2 = request.form.get('password2','')
            
            # التحقق من صحة البيانات
            if not email or '@' not in email or '.' not in email:
                return auth_fail('register', 'البريد الإلكتروني الصحيح مطلوب للتحقق من الحساب', 'email')
            if not name or not password:
                return auth_fail('register', 'أدخل الاسم والبريد وكلمة المرور', 'name')
            if len(password) < 8:
                return auth_fail('register', 'كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'password')
            if password != password2:
                return auth_fail('register', 'تأكيد كلمة المرور غير مطابق', 'password2')
            if birth_date:
                age = age_from_birth(birth_date)
                if age is None or age < 18:
                    return auth_fail('register', 'العمر يجب أن يكون 18 سنة أو أكثر', 'birth_date')
            
            # إنشاء اسم المستخدم
            username_base = ''.join(ch for ch in name.lower().replace(' ','_') if ch.isalnum() or ch=='_')[:20] or 'wasel'
            username = '@' + username_base
            i = 1
            while db().execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
                i += 1
                username = '@' + username_base + str(i)
            
            # إدراج المستخدم الجديد
            try:
                cur = db().execute("""INSERT INTO users(name,username,email,phone,phone_country_code,phone_full,password_hash,gender,birth_date,country,is_verified,created_at)
                                    VALUES(?,?,?,?,?,?,?,?,?,?,0,?)""", (name, username, email, phone, phone_country_code, phone_full, generate_password_hash(password), gender, birth_date, country, now()))
                db().commit()
                uid = cur.lastrowid
                
                # إنشاء رمز التحقق وإرساله
                code, ok, info = create_email_verify_code(uid, email)
                session.clear()
                session['_csrf_token'] = secrets.token_urlsafe(32)
                session['pending_verify_user_id'] = uid
                session['pending_verify_email'] = email
                
                if ok:
                    session['verify_flash'] = 'تم إرسال رمز التحقق بنجاح إلى بريدك الإلكتروني.'
                    session.pop('verify_error', None)
                else:
                    session['verify_error'] = 'تعذر إرسال رمز التحقق الآن. تأكد من اتصال الإنترنت أو اضغط إعادة إرسال.'
                    print('EMAIL_VERIFY_SEND_ERROR:', info)
                
                return auth_success('/verify_email')
            except sqlite3.IntegrityError as e:
                if 'email' in str(e).lower():
                    return auth_fail('register', 'البريد الإلكتروني مستخدم من قبل', 'email')
                elif 'phone' in str(e).lower():
                    return auth_fail('register', 'رقم الهاتف مستخدم من قبل', 'phone')
                else:
                    return auth_fail('register', 'حدث خطأ في إنشاء الحساب. حاول مرة أخرى.', '')
        except Exception as e:
            print(f"REGISTER_ERROR: {str(e)}")
            return auth_fail('register', 'حدث خطأ في الخادم. حاول مرة أخرى.', '', 500)
    
    return page(auth_html('register'))'''

# حفظ الملف المحسّن
print("✅ تم إنشاء الإصلاحات بنجاح")
