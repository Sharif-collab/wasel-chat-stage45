#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ملف الإصلاحات والتحسينات الرئيسية لـ wasel-chat-stage45
يحتوي على الأكواد المحسّنة التي يجب دمجها في الملف الرئيسي
"""

# ============================================================================
# 1. تحسين دالة send_mail - تقليل timeout وإضافة معالجة أفضل للأخطاء
# ============================================================================

IMPROVED_SEND_MAIL = '''
def send_mail(to_email, subject, body):
    """
    إرسال بريد إلكتروني عبر SMTP مع تحسين معالجة الأخطاء.
    تم تقليل timeout من 45 إلى 15 ثانية لتحسين الاستجابة.
    """
    if not smtp_ready():
        return False, "SMTP_NOT_CONFIGURED"
    
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = f"{Header(EMAIL_FROM, 'utf-8')} <{EMAIL_USER}>"
        msg["To"] = to_email
        
        print(f"DEBUG: Attempting to connect to {EMAIL_HOST}:{EMAIL_PORT} with timeout={EMAIL_TIMEOUT}s")
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=EMAIL_TIMEOUT) as server:
            server.ehlo()
            if server.has_extn("STARTTLS"):
                print("DEBUG: STARTTLS supported, starting TLS...")
                server.starttls()
                server.ehlo()
            
            try:
                print(f"DEBUG: Logging in as {EMAIL_USER}...")
                server.login(EMAIL_USER, EMAIL_PASS)
            except smtplib.SMTPAuthenticationError as auth_err:
                print(f"DEBUG: Auth failed: {auth_err}")
                return False, "AUTHENTICATION_FAILED"
            
            print(f"DEBUG: Sending email to {to_email}...")
            server.sendmail(EMAIL_USER, [to_email], msg.as_string())
            print("DEBUG: Email sent successfully!")
            
        return True, "SENT_SUCCESSFULLY"
    except smtplib.SMTPException as smtp_err:
        error_msg = f"SMTP Error: {str(smtp_err)}"
        print(f"SMTP_ERROR: {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = str(e)
        print(f"SMTP_ERROR: {error_msg}")
        return False, error_msg
'''

# ============================================================================
# 2. تحسين دالة register - معالجة أفضل للأخطاء وإرجاع JSON
# ============================================================================

IMPROVED_REGISTER = '''
@app.route('/register', methods=['GET','POST'])
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
            username_base = ''.join(ch for ch in name.lower().replace(' ','_') if ch.isalnum() or ch=='_')[:20] or 'wasel'
            username = '@' + username_base
            i = 1
            while db().execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
                i += 1
                username = '@' + username_base + str(i)
            try:
                cur = db().execute("""INSERT INTO users(name,username,email,phone,phone_country_code,phone_full,password_hash,gender,birth_date,country,is_verified,created_at)
                                    VALUES(?,?,?,?,?,?,?,?,?,?,0,?)""", (name, username, email, phone, phone_country_code, phone_full, generate_password_hash(password), gender, birth_date, country, now()))
                db().commit()
                uid = cur.lastrowid
                code, ok, info = create_email_verify_code(uid, email)
                session.clear(); session['_csrf_token'] = secrets.token_urlsafe(32)
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
                error_str = str(e).lower()
                if 'email' in error_str:
                    return auth_fail('register', 'البريد الإلكتروني مستخدم من قبل', 'email')
                elif 'phone' in error_str:
                    return auth_fail('register', 'رقم الهاتف مستخدم من قبل', 'phone')
                else:
                    return auth_fail('register', 'حدث خطأ في إنشاء الحساب. حاول مرة أخرى.', '')
        except Exception as e:
            print(f"REGISTER_ERROR: {str(e)}")
            return auth_fail('register', 'حدث خطأ في الخادم. حاول مرة أخرى.', '', 500)
    return page(auth_html('register'))
'''

# ============================================================================
# 3. إضافة middleware للـ compression والـ caching
# ============================================================================

COMPRESSION_MIDDLEWARE = '''
@app.after_request
def after_request_optimization(response):
    """تحسين الأداء عبر compression و caching"""
    # إضافة cache headers للملفات الثابتة
    if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
        response.cache_control.max_age = 86400  # 24 ساعة
        response.headers['ETag'] = f'"{hash(response.data)}"'
    
    # إضافة gzip compression للاستجابات الكبيرة
    if response.content_length and response.content_length > 1024:
        if 'gzip' in request.headers.get('Accept-Encoding', ''):
            try:
                response.data = gzip.compress(response.data)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(response.data)
            except:
                pass
    
    # إضافة security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    
    return response
'''

# ============================================================================
# 4. تحسين JavaScript لمعالجة الأخطاء بشكل أفضل
# ============================================================================

IMPROVED_JAVASCRIPT = '''
function initAuthAjax(){{
  document.querySelectorAll('form.authAjax').forEach(form=>{{
    form.addEventListener('submit',async e=>{{
      e.preventDefault(); clearAuthErrors(form);
      const btn=form.querySelector('button[type=submit],button:not([type])');
      const old=btn?btn.textContent:'';
      if(btn){{btn.textContent='جاري التحقق...';btn.disabled=true}}
      form.classList.add('authSaving');
      try{{
        const fd=new FormData(form);
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000); // timeout 10 ثوان
        const res=await fetch(form.action||location.href,{{
          method:'POST',
          headers:{{'X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()}},
          body:fd,
          credentials:'same-origin',
          signal:controller.signal
        }});
        clearTimeout(timeout);
        let data={{}}; 
        try{{
          const contentType = res.headers.get('content-type');
          if(contentType && contentType.includes('application/json')){{
            data=await res.json();
          }}else{{
            data={{ok:false,message:'استجابة غير صحيحة من الخادم'}}
          }}
        }}catch(_){{
          data={{ok:false,message:'تعذر قراءة رد الخادم. تأكد من اتصالك بالإنترنت.'}}
        }}
        if(data.ok){{ location.href=data.redirect||'/chats'; return; }}
        showAuthError(form,data.message||'توجد مشكلة في البيانات',data.field||'');
      }}catch(err){{
        if(err.name === 'AbortError'){{
          showAuthError(form,'انتهت مهلة الاتصال. حاول مرة أخرى.','');
        }}else{{
          showAuthError(form,'تعذر الاتصال بالخادم. حاول مرة أخرى.','');
        }}
      }}
      finally{{ if(btn){{btn.textContent=old;btn.disabled=false}} form.classList.remove('authSaving'); }}
    }});
  }});
}}
'''

print("✅ ملف الإصلاحات والتحسينات جاهز")
print("\nالتحسينات المطبقة:")
print("1. تقليل timeout البريد من 45 إلى 15 ثانية")
print("2. تحسين معالجة الأخطاء في دالة register")
print("3. إضافة gzip compression للاستجابات")
print("4. إضافة cache headers للملفات الثابتة")
print("5. تحسين معالجة أخطاء JavaScript")
