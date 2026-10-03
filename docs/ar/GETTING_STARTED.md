# الإعداد والتشغيل المحلي

[English](../GETTING_STARTED.md) · [الرئيسية بالعربية](../../README.ar.md)

**النسخة 0.2.0 أولية:** نجحت فحوص المصدر والبناء، لكن خطوات التثبيت الجديد والتشغيل العملي لهذه النسخة لم تُتحقق بعد. لا تعني الأوامر المنشورة أن التطبيق قد اجتاز الاختبارات التشغيلية.

## المتطلبات

تحتاج إلى Git وPython 3.12 وNode 24 ومتصفح محلي. يُستخدم Docker لجمع صفحات LAB أو PILOT فقط، ولا يلزم لمراجعة OFFLINE. يجب أن يكون محرك Docker محليًا من نوع Linux x64، مع دعم نمط البوابة المعزولة لمسار PILOT.

احفظ المشروع في مجلد محلي قابل للكتابة. يحتاج تثبيت التبعيات إلى الاتصال بمستودعات الحزم؛ كلمة OFFLINE تصف مراجعة الأدلة، وليست وعدًا بتثبيت دون إنترنت.

## 1. تجهيز المصدر

### Windows باستخدام PowerShell

```powershell
git clone https://github.com/OmarBajamel/checkout-evidence-monitor.git
cd checkout-evidence-monitor
git switch --detach v0.2.0-alpha.0
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --only-binary=:all: --require-hashes --no-compile -r requirements-dev-win.lock
Set-Location frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
Set-Location ..
.venv/Scripts/python -m build --no-isolation
.venv/Scripts/python -m pip install --no-deps --no-compile dist/checkout_evidence_monitor-0.2.0a0-py3-none-any.whl
```

### Linux باستخدام Bash

```bash
git clone https://github.com/OmarBajamel/checkout-evidence-monitor.git
cd checkout-evidence-monitor
git switch --detach v0.2.0-alpha.0
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes --no-compile -r requirements-dev-linux.lock
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
cd ..
.venv/bin/python -m build --no-isolation
.venv/bin/python -m pip install --no-deps --no-compile dist/checkout_evidence_monitor-0.2.0a0-py3-none-any.whl
```

هذه الأوامر تجهز التبعيات وتبني الحزمة؛ لا تشغّل التطبيق. إذا نزّلت أرشيف المصدر، فكّه وابدأ من إنشاء البيئة الافتراضية. لا تحذف متطلبات البصمات أو تغيّر حدود الأمان لتجاوز مشكلة توافق.

## 2. تشغيل العرض الاصطناعي بإذن صريح

نفّذ الأوامر التالية فقط عندما تختار السماح بالتشغيل المحلي للمصدر الذي جهزته. يسجّل الأمر نية المشغّل المحلي؛ لا يمثل تفويضًا قانونيًا أو إذنًا لزيارة متجر.

PowerShell:

```powershell
.venv/Scripts/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE
$env:CEM_TEST_SESSION=(Resolve-Path .cem-private/test-session.json).Path
.venv/Scripts/cem ui --demo
```

Bash:

```bash
.venv/bin/python tools/authorize_local.py --instruction 'TEST APPROVED' --profile OFFLINE
export CEM_TEST_SESSION="$PWD/.cem-private/test-session.json"
.venv/bin/cem ui --demo
```

افتح الرابط المحلي الذي يطبعه التطبيق خلال 60 ثانية. الرابط للاستخدام مرة واحدة، فلا تشاركه. يعرض هذا النمط بيانات اصطناعية في مخزن منفصل للقراءة فقط، ولا يبدأ جمع صفحات. أوقف الخادم باستخدام Ctrl+C.

لفتح مساحة فارغة قابلة للكتابة، احذف `--demo`. تُحفظ إعدادات المتجر بحالة متوقفة، ولا يبدأ فتح الواجهة عامل المراقبة. تغيير المصدر يُبطل الجلسة السابقة؛ أعد التفويض عمدًا عند الحاجة.

## 3. فهم دورة المراجعة

اختر سجلين مختلفين في `Assessments`: سجلًا مرجعيًا وآخر للمقارنة. افتح `Changes`، ثم افحص الدليل عبر `Evidence`. توضح `Journey` الحالات التي وصل إليها الرصد وحدوده.

لا يتيح العرض الاصطناعي حفظ قرارات المراجعة. استخدم مخزنًا قابلًا للكتابة وسجلات مناسبة منقحة لإتمام دورة المراجعة والتصدير.

## 4. الجمع والتعامل مع الأخطاء

الجمع مسار منفصل: اقرأ [دليل LAB](../RUNBOOK.md) أو [دليل PILOT](../PILOT_QUICKSTART.md) و[حدود أمانه](../PILOT_SECURITY.md). يتطلب المتجر الفعلي تفويضًا محدد الوجهات والإجراءات والمدة، وقبولًا صريحًا لحدود PILOT.

إذا ظهر `TEST_APPROVAL_REQUIRED` فتحقق من النمط وبصمة المصدر وصلاحية الجلسة. يعني `RUNNER_OFFLINE` أن عامل المراقبة غير جاهز؛ الواجهة العادية لا تبدأه. عند `CLEANUP_UNCONFIRMED` أوقف العمل الجديد واتبع دليل الاستعادة، ولا تتجاوز العزل.

عند الإبلاغ عن مشكلة، أرفق الإصدار والنمط ونظام التشغيل ورمز الخطأ الثابت. لا ترفق مفاتيح الوصول أو روابط الجلسات أو بيانات العملاء. [مصطلحات المشروع](GLOSSARY.md).
